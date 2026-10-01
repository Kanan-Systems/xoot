"""
A stored row that does not fit its model is a StoredDataError naming the
table, row, field and value, not a ValidationError that reads as the
caller's invalid input; free text is never echoed.
"""

from collections.abc import Callable

import pytest

from xoot.exceptions.stored_data_error import RESTART_HINT, StoredDataError
from xoot.models.event.entity_type import EntityType
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.repositories.event import event_db
from xoot.repositories.stored_row import from_row, shown_value
from xoot.store.store import Store


def test_unknown_event_client_names_the_row(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    foreign_event: Callable[[Item], int],
) -> None:
    """The event the old process could not read, reported as stored data."""
    goal = make_item(project, ItemKind.GOAL)
    event_id = foreign_event(goal)
    with store.read() as conn:
        with pytest.raises(StoredDataError) as caught:
            event_db.list_for_entity(conn, EntityType.ITEM, goal.id)
    error = caught.value
    assert (error.table, error.row_id, error.field) == ("event", event_id, "client")
    assert str(error) == (
        f"stored data could not be read: event row {event_id}, field client: "
        f"unexpected value 'telepathy'; {RESTART_HINT}"
    )
    assert "older xoot process may still be running" in str(error)


def test_free_text_is_described_not_shown() -> None:
    """A title or body that fails is never echoed."""
    secret = "my private note"
    with pytest.raises(StoredDataError) as caught:
        from_row(Project, "project", {"id": 4, "key_prefix": secret})
    assert secret not in str(caught.value)
    assert "project row 4" in str(caught.value)
    assert shown_value(secret) == "(text of 15 characters, not shown)"
    assert shown_value({"a": 1}) == "(a dict, not shown)"
    assert shown_value(True) == "(a bool, not shown)"
    assert shown_value("telepathy") == "'telepathy'"
    assert shown_value(7) == "7"


def test_a_row_without_an_id_says_unknown() -> None:
    """The row id is optional in the message."""
    with pytest.raises(StoredDataError, match="project row unknown, field"):
        from_row(Project, "project", {"key_prefix": "x"})
