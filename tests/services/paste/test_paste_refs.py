"""
Refs: an item_create, capture, backlog_cover or decision_record may name its
record, and later ops write "$<ref>" where a key goes. A ref is defined once,
used only after its defining op and only where its kind fits.
"""

from collections.abc import Callable
from typing import Any

import pytest

from xoot.exceptions.paste_error import PasteError
from xoot.exceptions.paste_op_error import PasteOpError
from xoot.models.project.project import Project
from xoot.repositories.item import item_db
from xoot.services.paste.models.paste_result import PasteResult
from xoot.services.paste.parser import parse_paste
from xoot.store.store import Store


def _create(ref: str, kind: str, parent: str | None = None) -> dict[str, Any]:
    op = {"op": "item_create", "ref": ref, "kind": kind, "title": f"{kind} {ref}"}
    return op if parent is None else {**op, "parent": parent}


def _decision(ref: str, owner: str) -> dict[str, Any]:
    return {
        "op": "decision_record",
        "ref": ref,
        "owner": owner,
        "title": "d",
        "body": "b",
        "status": "locked",
    }


def test_ref_chain_creates_links_and_updates(
    project: Project,
    store: Store,
    fenced: Callable[..., str],
    paste: Callable[[str], PasteResult],
) -> None:
    """goal -> batch under $goal -> subtask -> backlog on $sub -> update $sub."""
    result = paste(
        fenced(
            [
                _create("goal", "goal"),
                _create("batch", "batch", "$goal"),
                _create("sub", "subtask", "$batch"),
                {"op": "capture", "ref": "note", "found_on": "$sub", "title": "n"},
                {"op": "item_update", "key": "$sub", "changes": {"state": "active"}},
            ]
        )
    )
    assert result.refs == {
        "goal": "goal-1",
        "batch": "goal-1/batch-1",
        "sub": "goal-1/batch-1/subtask-1",
        "note": "goal-1/batch-1/backlog-1",
    }
    with store.read() as conn:
        goal, batch, sub, note = (
            item_db.get_by_key(conn, project.id, k) for k in result.refs.values()
        )
    assert goal and batch and sub and note
    assert (batch.parent_id, sub.parent_id) == (goal.id, batch.id)
    assert (note.parent_id, note.found_on_item_id) == (batch.id, sub.id)
    assert (sub.state, sub.version) == ("active", 2)


def test_forward_ref_names_the_op(fenced: Callable[..., str]) -> None:
    """A ref used before its defining op is refused with that op's number."""
    ops = [_create("batch", "batch", "$goal"), _create("goal", "goal")]
    with pytest.raises(
        PasteOpError,
        match=r"^op 1 \(item_create\): \$goal is not defined by an earlier op$",
    ):
        parse_paste(fenced(ops))


def test_undefined_ref_names_the_op(fenced: Callable[..., str]) -> None:
    """A ref never defined is refused the same way."""
    push = {"op": "backlog_push", "key": "$nope"}
    with pytest.raises(PasteOpError, match=r"^op 1 \(backlog_push\): \$nope"):
        parse_paste(fenced([push]))


def test_duplicate_ref_is_refused(fenced: Callable[..., str]) -> None:
    """A ref names one record."""
    ops = [_create("goal", "goal"), _create("goal", "goal")]
    with pytest.raises(
        PasteOpError, match=r"^op 2 \(item_create\): duplicate ref \$goal$"
    ):
        parse_paste(fenced(ops))


def test_duplicate_ref_across_kinds_is_refused(fenced: Callable[..., str]) -> None:
    """Items and decisions share one ref namespace."""
    ops = [_create("goal", "goal"), _decision("goal", "$goal")]
    with pytest.raises(PasteOpError, match=r"^op 2 \(decision_record\): duplicate"):
        parse_paste(fenced(ops))


def test_ref_of_the_wrong_kind_is_refused(fenced: Callable[..., str]) -> None:
    """A decision ref cannot be a parent."""
    ops = [_create("g", "goal"), _decision("d", "$g"), _create("b", "batch", "$d")]
    with pytest.raises(
        PasteOpError,
        match=r"^op 3 \(item_create\): \$d names a decision; an item is expected here$",
    ):
        parse_paste(fenced(ops))


def test_malformed_ref_is_refused_without_echo(fenced: Callable[..., str]) -> None:
    """A malformed ref fails the key grammar and is never repeated."""
    update = {"op": "item_update", "key": "$Bad-Ref!", "changes": {"state": "done"}}
    with pytest.raises(PasteError) as caught:
        parse_paste(fenced([update]))
    assert "op 1 (item_update): key (item_key)" in str(caught.value)
    assert "Bad-Ref" not in str(caught.value)


def test_expected_version_must_be_omitted_for_a_ref(fenced: Callable[..., str]) -> None:
    """The block created the item, so it knows the version."""
    update = {
        "op": "item_update",
        "key": "$g",
        "expected_version": 1,
        "changes": {"state": "active"},
    }
    with pytest.raises(
        PasteOpError, match=r"^op 2 \(item_update\): omit expected_version"
    ):
        parse_paste(fenced([_create("g", "goal"), update]))


@pytest.mark.parametrize("op", ["item_update", "decision_update"])
def test_expected_version_is_required_for_a_key(
    fenced: Callable[..., str], op: str
) -> None:
    """An existing record needs the version the chat last saw."""
    key = "goal-1" if op == "item_update" else "goal-1/decision-1"
    update = {"op": op, "key": key, "changes": {"title": "t"}}
    with pytest.raises(
        PasteOpError, match=rf"^op 1 \({op}\): expected_version is required"
    ):
        parse_paste(fenced([update]))
