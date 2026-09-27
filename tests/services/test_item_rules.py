"""T5: the goal > batch > subtask hierarchy, in the service and the database."""

from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.exceptions.hierarchy_error import HierarchyError
from xoot.exceptions.integrity_violation_error import IntegrityViolationError
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.new_item import NewItem
from xoot.models.project.project import Project
from xoot.repositories.item import item_db
from xoot.services.item_rules import check_child_kind
from xoot.store.store import Store

GOAL, BATCH, SUBTASK = ItemKind.GOAL, ItemKind.BATCH, ItemKind.SUBTASK


@pytest.fixture(name="parents")
def fixture_parents(
    project: Project, make_item: Callable[..., Item]
) -> dict[ItemKind, Item]:
    """One item of each kind, correctly nested, to use as parents."""
    goal = make_item(project, GOAL)
    batch = make_item(project, BATCH, parent_id=goal.id)
    subtask = make_item(project, SUBTASK, parent_id=batch.id)
    return {GOAL: goal, BATCH: batch, SUBTASK: subtask}


@pytest.mark.parametrize(
    ("kind", "parent_kind"),
    [(GOAL, None), (BATCH, GOAL), (SUBTASK, BATCH), (SUBTASK, None)],
)
def test_allowed_parents(
    project: Project,
    parents: dict[ItemKind, Item],
    make_item: Callable[..., Item],
    kind: ItemKind,
    parent_kind: ItemKind | None,
) -> None:
    """Goal at the top, batch under goal, subtask under batch or unfiled."""
    parent_id = None if parent_kind is None else parents[parent_kind].id
    item = make_item(project, kind, parent_id=parent_id)
    assert item.parent_id == parent_id
    assert item.unfiled is (kind is SUBTASK and parent_id is None)


@pytest.mark.parametrize(
    ("kind", "parent_kind"),
    [
        (GOAL, GOAL),
        (GOAL, BATCH),
        (BATCH, None),
        (BATCH, BATCH),
        (BATCH, SUBTASK),
        (SUBTASK, GOAL),
        (SUBTASK, SUBTASK),
    ],
)
def test_forbidden_parents(
    project: Project,
    parents: dict[ItemKind, Item],
    make_item: Callable[..., Item],
    kind: ItemKind,
    parent_kind: ItemKind | None,
) -> None:
    """Every other combination is a hierarchy violation."""
    parent_id = None if parent_kind is None else parents[parent_kind].id
    with pytest.raises(HierarchyError):
        make_item(project, kind, parent_id=parent_id)


@pytest.mark.parametrize(("kind", "parent_kind"), [(BATCH, GOAL), (SUBTASK, BATCH)])
def test_cross_project_parent_is_rejected(
    other_project: Project,
    parents: dict[ItemKind, Item],
    make_item: Callable[..., Item],
    kind: ItemKind,
    parent_kind: ItemKind,
) -> None:
    """A parent of the right kind but in another project is still rejected."""
    with pytest.raises(CrossProjectError):
        make_item(other_project, kind, parent_id=parents[parent_kind].id)


def _raw_item(owner: Project, kind: ItemKind, parent_id: int) -> NewItem:
    """An item row built directly, bypassing every service check."""
    return NewItem(
        project_id=owner.id,
        number=99,
        key=f"{owner.key_prefix}-99",
        kind=kind,
        parent_id=parent_id,
        title="raw",
        body="",
        state="open",
        backlog_session_id=None,
        awaiting_decision_id=None,
        created_at=datetime.now(UTC),
    )


@pytest.mark.parametrize(("kind", "parent_kind"), [(SUBTASK, GOAL), (BATCH, BATCH)])
def test_database_rejects_wrong_parent_kind(
    store: Store,
    project: Project,
    parents: dict[ItemKind, Item],
    kind: ItemKind,
    parent_kind: ItemKind,
) -> None:
    """The schema's parent foreign key enforces the hierarchy by itself."""
    with pytest.raises(IntegrityViolationError, match="FOREIGN KEY"):
        with store.write() as conn:
            item_db.insert(conn, _raw_item(project, kind, parents[parent_kind].id))


def test_database_rejects_cross_project_parent(
    store: Store, other_project: Project, parents: dict[ItemKind, Item]
) -> None:
    """The composite foreign key keeps parents inside the child's project."""
    with pytest.raises(IntegrityViolationError, match="FOREIGN KEY"):
        with store.write() as conn:
            item_db.insert(conn, _raw_item(other_project, BATCH, parents[GOAL].id))


@pytest.mark.parametrize("parent_kind", list(ItemKind))
@pytest.mark.parametrize("kind", list(ItemKind))
def test_child_kind_follows_the_hierarchy(
    parent_kind: ItemKind, kind: ItemKind
) -> None:
    """A planned parent allows exactly goal > batch and batch > subtask."""
    if (parent_kind, kind) in {(GOAL, BATCH), (BATCH, SUBTASK)}:
        check_child_kind(parent_kind, kind)
    else:
        with pytest.raises(HierarchyError):
            check_child_kind(parent_kind, kind)
