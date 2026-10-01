"""
item_get over an event this code cannot read: the tool error says stored
data could not be read, not "invalid arguments"; true input errors keep
their ValidationError text.
"""

from collections.abc import Callable
from typing import Any

from mcp import ClientSession

from xoot.exceptions.stored_data_error import RESTART_HINT
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project


def test_item_get_reports_unreadable_stored_data(
    harness: Any,
    project: Project,
    make_item: Callable[..., Item],
    foreign_event: Callable[[Item], int],
) -> None:
    """The message names the table, row, field, value and the restart hint."""
    goal = make_item(project, ItemKind.GOAL)
    event_id = foreign_event(goal)

    async def scenario(client: ClientSession) -> tuple[str, str]:
        return (
            await harness.error(client, "item_get", key=goal.key, project="xoot"),
            await harness.error(client, "tree_get", project="xoot", depth=-1),
        )

    stored, invalid = harness.run(scenario)
    assert stored == (
        "Error executing tool item_get: StoredDataError: stored data could not "
        f"be read: event row {event_id}, field client: unexpected value "
        f"'telepathy'; {RESTART_HINT}"
    )
    assert "invalid arguments" not in stored
    assert "ValidationError: invalid arguments: depth" in invalid
