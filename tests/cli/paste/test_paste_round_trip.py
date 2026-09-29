"""
A full round trip: the brief gives versions; block A creates a goal, works
it and captures backlog; its receipt gives keys and versions; block B covers
the backlog item, finishes the work, and the goal completes.
"""

import json
import re
from collections.abc import Callable
from typing import Any

from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services.item_service import get_item
from xoot.store.store import Store


def test_brief_then_two_blocks_with_receipt_versions(
    project: Project,
    store: Store,
    make_item: Callable[..., Item],
    paste_cli: Callable[..., Any],
    reply: Callable[..., bytes],
) -> None:
    """Block B uses block A's receipt; the receipts report what completed."""
    existing = make_item(project, ItemKind.GOAL, state="active")
    brief = paste_cli("paste", "brief", "--project", "xoot").out
    version = int(re.search(rf"`{existing.key}` active v(\d+)", brief).group(1))

    block_a = [
        {"op": "item_create", "ref": "g", "kind": "goal", "title": "export"},
        {"op": "item_create", "ref": "b", "kind": "batch", "title": "writer",
         "parent": "$g"},
        {"op": "item_create", "ref": "t", "kind": "subtask", "title": "rows",
         "parent": "$b"},
        {"op": "capture", "ref": "c", "found_on": "$t", "title": "BOM",
         "body": "Excel adds one"},
        {"op": "item_update", "key": "$t", "changes": {"state": "done"}},
        {"op": "item_update", "key": existing.key, "expected_version": version,
         "changes": {"title": "renamed"}},
    ]  # fmt: skip
    run_a = paste_cli("paste", "apply", "-", "--yes", stdin=reply(block_a))
    assert run_a.code == 0, run_a.err
    receipt = run_a.receipt()
    assert receipt["refs"] == {
        "g": "goal-2",
        "b": "goal-2/batch-1",
        "t": "goal-2/batch-1/subtask-1",
        "c": "goal-2/batch-1/backlog-1",
    }
    assert receipt["blocked"] == [{"key": "goal-2/batch-1", "open_backlog": 1}]
    versions = {item["key"]: item["version"] for item in receipt["items"]}

    block_b = [
        {"op": "backlog_cover", "ref": "s", "key": receipt["refs"]["c"]},
        {"op": "item_update", "key": "$s", "changes": {"state": "done"}},
        {"op": "item_update", "key": existing.key,
         "expected_version": versions[existing.key], "changes": {"state": "done"}},
    ]  # fmt: skip
    run_b = paste_cli("paste", "apply", "-", "--yes", stdin=reply(block_b))
    assert run_b.code == 0, run_b.err
    final = run_b.receipt()
    assert final["refs"] == {"s": "goal-2/batch-1/subtask-2"}
    assert final["completed"] == ["goal-2/batch-1", "goal-2"]
    assert final["blocked"] == []
    assert "COMPLETION" in run_b.err
    assert get_item(store, existing.id).state == "done"
    assert json.dumps(final).count("Excel") == 0
