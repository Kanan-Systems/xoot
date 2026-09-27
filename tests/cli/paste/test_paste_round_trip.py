"""
A full round trip: the brief gives versions, block A starts a session and
changes items, its receipt gives new versions, and block B uses them to
update again and close the session.
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
    """Block B passes the versions block A's receipt reported."""
    goal = make_item(project, ItemKind.GOAL, state="active")
    brief = paste_cli("paste", "brief", "--project", "xoot").out
    version = int(re.search(rf"`{goal.key}` goal active v(\d+)", brief).group(1))

    block_a = [
        {"op": "session_start", "title": "round trip", "focus": [goal.key]},
        {"op": "item_create", "ref": "b", "kind": "batch", "title": "b", "parent": goal.key},
        {"op": "item_update", "key": goal.key, "expected_version": version,
         "changes": {"title": "renamed goal"}},
    ]  # fmt: skip
    first = paste_cli("paste", "apply", "-", "--yes", stdin=reply(block_a))
    assert first.code == 0, first.err
    receipt = first.receipt()
    versions = {entry["key"]: entry["version"] for entry in receipt["items"]}

    block_b = [
        {"op": "item_update", "key": goal.key, "expected_version": versions[goal.key],
         "changes": {"state": "done"}},
        {"op": "item_update", "key": receipt["refs"]["b"],
         "expected_version": versions[receipt["refs"]["b"]],
         "changes": {"state": "done"}},
        {"op": "session_close", "summary": "all done", "dispositions": {}},
    ]  # fmt: skip
    second = paste_cli(
        "paste", "apply", "-", "--yes", stdin=reply(block_b, session=receipt["session"])
    )
    assert second.code == 0, second.err
    final = second.receipt()
    assert final["session_status"] == "closed"
    assert {e["key"]: (e["state"], e["version"]) for e in final["items"]} == {
        goal.key: ("done", 3),
        receipt["refs"]["b"]: ("done", 2),
    }
    assert get_item(store, goal.id).title == "renamed goal"
    assert json.loads(json.dumps(final)) == final
