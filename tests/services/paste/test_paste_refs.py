"""
Refs: an item_create or decision_record may name its record, and later ops
write "$<ref>" where a key goes. A ref is defined once, used only after its
defining op and only where its kind fits; the session is never a ref.
"""

from collections.abc import Callable
from typing import Any

import pytest

from xoot.exceptions.paste_op_error import PasteOpError
from xoot.models.project.project import Project
from xoot.models.session.disposition import Disposition
from xoot.models.session.session_status import SessionStatus
from xoot.repositories.item import item_db
from xoot.repositories.session import session_item_ref_db
from xoot.services.paste.models.paste_result import PasteResult
from xoot.services.paste.parser import parse_paste
from xoot.store.store import Store

START = {"op": "session_start", "title": "plan"}


def _create(ref: str, kind: str, parent: str | None = None) -> dict[str, Any]:
    op = {"op": "item_create", "ref": ref, "kind": kind, "title": f"{kind} {ref}"}
    return op if parent is None else {**op, "parent": parent}


def test_ref_chain_creates_links_and_closes(
    project: Project,
    store: Store,
    fenced: Callable[..., str],
    paste: Callable[[str], PasteResult],
) -> None:
    """goal -> batch under $goal -> subtask -> update $sub -> close with $refs."""
    result = paste(
        fenced(
            [
                START,
                _create("goal", "goal"),
                _create("batch", "batch", "$goal"),
                _create("sub", "subtask", "$batch"),
                {"op": "item_update", "key": "$sub", "changes": {"state": "active"}},
                {
                    "op": "session_close",
                    "dispositions": {
                        "$goal": "carry_over",
                        "$batch": "carry_over",
                        "$sub": "session_backlog",
                    },
                },
            ]
        )
    )
    assert result.refs == {"goal": "xoot-1", "batch": "xoot-2", "sub": "xoot-3"}
    with store.read() as conn:
        goal, batch, sub = (item_db.get_by_key(conn, k) for k in result.refs.values())
        refs = session_item_ref_db.list_for_session(conn, 1)
    assert goal is not None and batch is not None and sub is not None
    assert (batch.parent_id, sub.parent_id) == (goal.id, batch.id)
    assert (sub.state, sub.version, sub.backlog_session_id) == ("backlogged", 3, 1)
    assert {r.item_id: r.disposition for r in refs} == {
        goal.id: Disposition.CARRY_OVER,
        batch.id: Disposition.CARRY_OVER,
        sub.id: Disposition.SESSION_BACKLOG,
    }
    assert (result.session, result.session_status) == ("xoot-S1", SessionStatus.CLOSED)
    assert project.key_prefix == result.project


def test_forward_ref_names_the_op(fenced: Callable[..., str]) -> None:
    """A ref used before its defining op is refused with that op's number."""
    ops = [START, _create("batch", "batch", "$goal"), _create("goal", "goal")]
    with pytest.raises(
        PasteOpError,
        match=r"^op 2 \(item_create\): \$goal is not defined by an earlier op$",
    ):
        parse_paste(fenced(ops))


def test_undefined_ref_names_the_op(fenced: Callable[..., str]) -> None:
    """A ref never defined is refused the same way."""
    close = {"op": "session_close", "dispositions": {"$nope": "dropped"}}
    with pytest.raises(PasteOpError, match=r"^op 2 \(session_close\): \$nope"):
        parse_paste(fenced([START, close]))


def test_duplicate_ref_is_refused(fenced: Callable[..., str]) -> None:
    """A ref names one record."""
    ops = [START, _create("goal", "goal"), _create("goal", "goal")]
    with pytest.raises(
        PasteOpError, match=r"^op 3 \(item_create\): duplicate ref \$goal$"
    ):
        parse_paste(fenced(ops))


def test_duplicate_ref_across_kinds_is_refused(fenced: Callable[..., str]) -> None:
    """Items and decisions share one ref namespace."""
    decision = {
        "op": "decision_record",
        "ref": "goal",
        "title": "d",
        "body": "b",
        "status": "locked",
    }
    with pytest.raises(PasteOpError, match=r"^op 3 \(decision_record\): duplicate"):
        parse_paste(fenced([START, _create("goal", "goal"), decision]))


def test_ref_of_the_wrong_kind_is_refused(fenced: Callable[..., str]) -> None:
    """A decision ref cannot be a parent."""
    decision = {
        "op": "decision_record",
        "ref": "d",
        "title": "d",
        "body": "b",
        "status": "locked",
    }
    with pytest.raises(
        PasteOpError,
        match=r"^op 3 \(item_create\): \$d names a decision; an item is expected here$",
    ):
        parse_paste(fenced([START, decision, _create("b", "batch", "$d")]))


def test_session_is_never_a_ref(fenced: Callable[..., str]) -> None:
    """backlog_session takes a session key, never $."""
    update = {
        "op": "item_update",
        "key": "$g",
        "changes": {"backlog_session": "$g"},
    }
    with pytest.raises(
        PasteOpError, match=r"^op 3 \(item_update\): a session is never"
    ):
        parse_paste(fenced([START, _create("g", "goal"), update]))


def test_malformed_ref_is_refused_without_echo(fenced: Callable[..., str]) -> None:
    """Only a well-formed ref name is ever repeated."""
    update = {"op": "item_update", "key": "$Bad-Ref!", "changes": {"state": "done"}}
    with pytest.raises(PasteOpError, match=r"^op 2 \(item_update\): malformed ref$"):
        parse_paste(fenced([START, update]))


def test_expected_version_must_be_omitted_for_a_ref(fenced: Callable[..., str]) -> None:
    """The block created the item, so it knows the version."""
    update = {
        "op": "item_update",
        "key": "$g",
        "expected_version": 1,
        "changes": {"state": "active"},
    }
    with pytest.raises(
        PasteOpError, match=r"^op 3 \(item_update\): omit expected_version"
    ):
        parse_paste(fenced([START, _create("g", "goal"), update]))


@pytest.mark.parametrize("op", ["item_update", "decision_update"])
def test_expected_version_is_required_for_a_key(
    fenced: Callable[..., str], op: str
) -> None:
    """An existing record needs the version the chat last saw."""
    key = "xoot-1" if op == "item_update" else "xoot-D1"
    update = {"op": op, "key": key, "changes": {"title": "t"}}
    with pytest.raises(
        PasteOpError, match=rf"^op 2 \({op}\): expected_version is required"
    ):
        parse_paste(fenced([START, update]))
