"""The CLI reports unreadable stored data as such, with exit code 3."""

from collections.abc import Callable
from typing import Any

from xoot.cli import exit_codes
from xoot.exceptions.stored_data_error import RESTART_HINT
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services.item_service import get_item
from xoot.store.store import Store


def test_redact_over_an_unreadable_event(
    xoot: Any,
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    foreign_event: Callable[[Item], int],
) -> None:
    """Redaction reads the item's history; the unknown client stops it and
    nothing is written."""
    goal = make_item(project, ItemKind.GOAL, title="kept")
    event_id = foreign_event(goal)
    run = xoot("redact", f"xoot:{goal.key}", "title", "--yes")
    assert run.code == exit_codes.UNAVAILABLE
    assert run.err == (
        f"error: StoredDataError: stored data could not be read: event row "
        f"{event_id}, field client: unexpected value 'telepathy'; {RESTART_HINT}\n"
    )
    assert "invalid arguments" not in run.err
    assert get_item(store, goal.id).title == "kept"


def test_input_validation_keeps_its_text(xoot: Any, project: Project) -> None:
    """A true input error is still a ValidationError line with exit code 1."""
    assert project.key_prefix == "xoot"
    run = xoot("project", "add-alias", "Not A Slug", "--project", "xoot")
    assert run.code == exit_codes.ERROR
    assert run.err.startswith("error: ValidationError: alias: ")
