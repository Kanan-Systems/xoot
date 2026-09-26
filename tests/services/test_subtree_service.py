"""F7: subtree drop and reparent, each a pure preview plus a re-validating apply."""

from collections.abc import Callable

import pytest

from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.exceptions.hierarchy_error import HierarchyError
from xoot.exceptions.version_conflict_error import VersionConflictError
from xoot.models.event.actor import Actor
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.repositories.session import session_item_ref_db
from xoot.services.item_service import get_item
from xoot.services.subtree_service import (
    apply_drop,
    apply_reparent,
    preview_drop,
    preview_reparent,
)
from xoot.store.store import Store


@pytest.fixture(name="tree")
def fixture_tree(project: Project, make_item: Callable[..., Item]) -> dict[str, Item]:
    """goal > batch > (open subtask, done subtask), plus a second goal."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    return {
        "goal": goal,
        "batch": batch,
        "open": make_item(project, ItemKind.SUBTASK, parent_id=batch.id),
        "done": make_item(project, ItemKind.SUBTASK, parent_id=batch.id, state="done"),
        "goal2": make_item(project, ItemKind.GOAL),
    }


def test_drop_preview_writes_nothing(
    store: Store, tree: dict[str, Item], row_counts: Callable[[], dict[str, int]]
) -> None:
    """The preview lists every non-terminal item in the subtree, and writes nothing."""
    before, changes = row_counts(), store.conn.total_changes
    plan = preview_drop(store, tree["goal"].id)
    assert (row_counts(), store.conn.total_changes) == (before, changes)
    assert [c.item_id for c in plan.changes] == [
        tree[k].id for k in ("goal", "batch", "open")
    ]
    assert all(c.after == {"state": "dropped"} for c in plan.changes)


def test_drop_apply_writes_the_plan(
    store: Store, tree: dict[str, Item], ctx: WriteContext
) -> None:
    """Apply drops the same items; done items keep their state."""
    preview = preview_drop(store, tree["goal"].id)
    assert apply_drop(store, tree["goal"].id, 1, ctx) == preview
    assert [
        get_item(store, tree[k].id).state for k in ("goal", "batch", "open", "done")
    ] == [
        "dropped",
        "dropped",
        "dropped",
        "done",
    ]
    assert get_item(store, tree["goal2"].id) == tree["goal2"]


def test_apply_revalidates_against_current_rows(
    store: Store,
    project: Project,
    tree: dict[str, Item],
    make_item: Callable[..., Item],
    ctx: WriteContext,
) -> None:
    """Apply re-plans: a child added after the preview is dropped too."""
    preview = preview_drop(store, tree["batch"].id)
    late = make_item(project, ItemKind.SUBTASK, parent_id=tree["batch"].id)
    applied = apply_drop(store, tree["batch"].id, 1, ctx)
    assert late.id in {c.item_id for c in applied.changes} - {
        c.item_id for c in preview.changes
    }


def test_drop_checks_the_root_version(
    store: Store, tree: dict[str, Item], ctx: WriteContext
) -> None:
    """A stale root version refuses the whole drop."""
    with pytest.raises(VersionConflictError):
        apply_drop(store, tree["goal"].id, 7, ctx)
    assert get_item(store, tree["open"].id).state == "open"


def test_reparent_preview(
    store: Store, tree: dict[str, Item], row_counts: Callable[[], dict[str, int]]
) -> None:
    """Only the root row would change; descendants are carried; nothing written."""
    before = row_counts()
    plan = preview_reparent(store, tree["batch"].id, tree["goal2"].id)
    assert row_counts() == before
    assert [(c.item_id, c.before, c.after) for c in plan.changes] == [
        (
            tree["batch"].id,
            {"parent_id": tree["goal"].id},
            {"parent_id": tree["goal2"].id},
        )
    ]
    assert plan.carried_item_ids == (tree["open"].id, tree["done"].id)


def test_reparent_apply(
    store: Store,
    project: Project,
    tree: dict[str, Item],
    make_session: Callable[..., Session],
    user: Actor,
) -> None:
    """Apply moves the root, keeps the children under it, and links the root."""
    session = make_session(project)
    in_session = WriteContext(actor=user, session_id=session.id)
    plan = apply_reparent(store, tree["batch"].id, tree["goal2"].id, 1, in_session)
    assert [c.item_id for c in plan.changes] == [tree["batch"].id]
    assert get_item(store, tree["batch"].id).parent_id == tree["goal2"].id
    assert get_item(store, tree["open"].id).parent_id == tree["batch"].id
    with store.read() as conn:
        assert session_item_ref_db.open_session_ids(conn, tree["batch"].id) == [
            session.id
        ]


def test_reparent_to_unfiled(
    store: Store, tree: dict[str, Item], ctx: WriteContext
) -> None:
    """A subtask can be detached from its batch."""
    apply_reparent(store, tree["open"].id, None, 1, ctx)
    assert get_item(store, tree["open"].id).unfiled


def test_reparent_enforces_the_hierarchy(
    store: Store,
    other_project: Project,
    tree: dict[str, Item],
    make_item: Callable[..., Item],
) -> None:
    """Previews reject bad parents too, not only applies."""
    with pytest.raises(HierarchyError):
        preview_reparent(store, tree["batch"].id, None)
    with pytest.raises(HierarchyError):
        preview_reparent(store, tree["batch"].id, tree["open"].id)
    foreign = make_item(other_project, ItemKind.GOAL)
    with pytest.raises(CrossProjectError):
        preview_reparent(store, tree["batch"].id, foreign.id)
