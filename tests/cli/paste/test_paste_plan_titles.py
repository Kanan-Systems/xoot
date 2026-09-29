"""
The plan names every created, updated and completed item by kind and title,
and every decision by title: cut at 60 characters and escaped, so what the
user confirms is readable and cannot drive the terminal.
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
    """Created, updated, completed items and decisions all carry titles."""
    goal = make_item(project, ItemKind.GOAL, title=f"old {ESCAPED}")
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id, title="b")
    task = make_item(project, ItemKind.SUBTASK, parent_id=batch.id, title="t")
    ops = [
        {"op": "item_create", "ref": "g", "kind": "goal", "title": LONG},
        {"op": "item_update", "key": task.key, "expected_version": 1,
         "changes": {"state": "done"}},
        {"op": "decision_record", "owner": goal.key, "title": f"decide {ESCAPED}",
         "body": "b", "status": "locked"},
    ]  # fmt: skip
    run = paste_cli("paste", "apply", "-", "--yes", stdin=reply(ops))
    assert run.code == 0, run.err
    shown = "\\u001b[31mred\\u202eevil"
    lines = run.err.splitlines()
    assert f'  op 1 item_create: goal-2 (new, $g) goal "{"L" * 60}"' in lines
    assert '  op 2 item_update: goal-1/batch-1/subtask-1 subtask "t"' in lines
    assert (
        f'  op 3 decision_record: goal-1/decision-1 (new) decision "decide {shown}"'
        in lines
    )
    assert '  completes goal-1/batch-1 batch "b"' in lines
    assert f'  completes goal-1 goal "old {shown}"' in lines
    assert "L" * 61 not in run.err
    assert "\x1b" not in run.err and "\u202e" not in run.err
    assert "L" * 60 not in run.out and "old" not in run.out
