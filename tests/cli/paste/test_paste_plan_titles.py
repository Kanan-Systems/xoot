"""
The plan names every created, updated, disposed and auto-backlogged item by
kind and title, and every decision by title: cut at 60 characters and
escaped, so what the user confirms is readable and cannot drive the terminal.
"""

from collections.abc import Callable
from typing import Any

from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project

ESCAPED = "\x1b[31mred\u202eevil"
LONG = "L" * 70


def test_plan_names_records_by_kind_and_escaped_title(
    project: Project,
    make_item: Callable[..., Item],
    paste_cli: Callable[..., Any],
    reply: Callable[..., bytes],
) -> None:
    """Created, updated, disposed, side-effect items and decisions all carry titles."""
    existing = make_item(project, ItemKind.GOAL, title=f"old {ESCAPED}")
    park = [
        {"op": "session_start", "title": "first"},
        {
            "op": "item_create",
            "ref": "p",
            "kind": "subtask",
            "title": f"parked {ESCAPED}",
        },
        {"op": "session_close", "dispositions": {"$p": "session_backlog"}},
    ]
    assert paste_cli("paste", "apply", "-", "--yes", stdin=reply(park)).code == 0
    ops = [
        {"op": "session_start", "title": "second"},
        {"op": "item_create", "ref": "g", "kind": "goal", "title": LONG},
        {"op": "item_update", "key": existing.key, "expected_version": 1,
         "changes": {"state": "active"}},
        {"op": "decision_record", "title": f"decide {ESCAPED}", "body": "b",
         "status": "locked"},
        {"op": "session_close", "dispositions": {"$g": "carry_over",
                                                 existing.key: "dropped"}},
    ]  # fmt: skip
    run = paste_cli("paste", "apply", "-", "--yes", stdin=reply(ops))
    assert run.code == 0, run.err
    shown = "\\u001b[31mred\\u202eevil"
    lines = run.err.splitlines()
    assert f'  op 2 item_create: xoot-3 (new, $g) goal "{"L" * 60}"' in lines
    assert f'  op 3 item_update: xoot-1 goal "old {shown}"' in lines
    assert f'  op 4 decision_record: xoot-D1 (new) decision "decide {shown}"' in lines
    assert f'      dispose xoot-3 goal "{"L" * 60}": carry_over' in lines
    assert f'      dispose xoot-1 goal "old {shown}": dropped' in lines
    assert (
        f'  xoot-2 subtask "parked {shown}": moves from the backlog of xoot-S1 '
        "to the project backlog"
    ) in lines
    assert "L" * 61 not in run.err
    assert "\x1b" not in run.err and "\u202e" not in run.err
    assert "L" * 60 not in run.out and "old" not in run.out
