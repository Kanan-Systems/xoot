"""
capture takes an optional ref, with item_create's rules, so a block can
capture a side item and dispose of it in its own session_close.
"""

import json
from collections.abc import Callable
from typing import Any

import pytest

from xoot.exceptions.paste_error import PasteError
from xoot.exceptions.paste_op_error import PasteOpError
from xoot.models.item.item_kind import ItemKind
from xoot.repositories.item import item_db
from xoot.services.paste.parser import parse_paste
from xoot.store.store import Store

START = {"op": "session_start", "title": "plan"}


@pytest.mark.usefixtures("project")
def test_capture_ref_is_disposed_and_mapped(
    paste_cli: Callable[..., Any], reply: Callable[..., bytes], store: Store
) -> None:
    """capture $side -> update $side -> close with a $side disposition."""
    ops = [
        START,
        {"op": "capture", "ref": "side", "title": "side note"},
        {"op": "item_update", "key": "$side", "changes": {"title": "renamed"}},
        {"op": "session_close", "dispositions": {"$side": "project_backlog"}},
    ]
    run = paste_cli("paste", "apply", "-", "--yes", stdin=reply(ops))
    assert run.code == 0, run.err
    receipt = run.receipt()
    assert receipt["refs"] == {"side": "xoot-1"}
    with store.read() as conn:
        item = item_db.get_by_key(conn, receipt["refs"]["side"])
    assert item is not None and item.kind is ItemKind.SUBTASK
    assert (item.title, item.state, item.backlog_session_id) == (
        "renamed",
        "backlogged",
        None,
    )


def test_capture_ref_follows_the_ref_rules() -> None:
    """Refs are unique across ops and shape-checked like item_create's."""
    capture = {"op": "capture", "ref": "a", "title": "c"}
    create = {"op": "item_create", "ref": "a", "kind": "goal", "title": "g"}
    with pytest.raises(
        PasteOpError, match=r"^op 3 \(item_create\): duplicate ref \$a$"
    ):
        parse_paste(_block([START, capture, create]))
    with pytest.raises(
        PasteError, match=r"op 2 \(capture\): ref \(string_pattern_mismatch\)"
    ):
        parse_paste(_block([START, {**capture, "ref": "Bad"}]))


def _block(ops: list[dict[str, str]]) -> str:
    return f"```xoot\n{json.dumps({'xoot': 1, 'project': 'xoot', 'ops': ops})}\n```"
