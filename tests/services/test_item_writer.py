"""Planning and writing item changes: diffs, no-ops and version bumps."""

from collections.abc import Callable

from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services.item_service import get_item
from xoot.services.item_writer import apply_changes, plan_change, write_item
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store


def test_plan_change_lists_only_real_changes(
    project: Project, make_item: Callable[..., Item]
) -> None:
    """Setting a field to its current value is not a change."""
    item = make_item(project, ItemKind.GOAL)
    assert plan_change(item, {"state": "open"}) is None
    change = plan_change(item, {"state": "active", "title": item.title})
    assert change is not None
    assert (change.key, change.before, change.after) == (
        "xoot-1",
        {"state": "open"},
        {"state": "active"},
    )


def test_write_item_bumps_version_or_does_nothing(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    ctx: WriteContext,
    event_kinds: Callable[[Project], list[tuple[str, str]]],
) -> None:
    """A real change bumps the version and records one event; a no-op neither."""
    item = make_item(project, ItemKind.GOAL)
    before = len(event_kinds(project))
    with store.write() as conn:
        scope = WriteScope(conn, ctx)
        assert write_item(scope, item, {"title": item.title}) is item
        updated = write_item(scope, item, {"title": "new"})
    assert (updated.version, updated.updated_at) == (2, scope.now)
    assert get_item(store, item.id) == updated
    assert event_kinds(project)[before:] == [("item", "update")]


def test_apply_changes_rereads_each_item(
    store: Store, project: Project, make_item: Callable[..., Item], ctx: WriteContext
) -> None:
    """Planned changes are applied to the current rows, in order."""
    first, second = make_item(project, ItemKind.GOAL), make_item(project, ItemKind.GOAL)
    changes = [plan_change(item, {"state": "blocked"}) for item in (first, second)]
    with store.write() as conn:
        written = apply_changes(WriteScope(conn, ctx), [c for c in changes if c])
    assert [(i.id, i.state, i.version) for i in written] == [
        (first.id, "blocked", 2),
        (second.id, "blocked", 2),
    ]
