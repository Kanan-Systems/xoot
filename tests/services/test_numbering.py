"""Numbers are allocated per parent, never reused, and build nested keys."""

from collections.abc import Callable

import pytest

from xoot.exceptions.hierarchy_error import HierarchyError
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services.item_service import create_item
from xoot.store.store import Store


def test_numbers_restart_under_each_parent(
    project: Project, make_item: Callable[..., Item]
) -> None:
    """Each goal numbers its own batches, each batch its own subtasks."""
    first_goal = make_item(project, ItemKind.GOAL)
    second_goal = make_item(project, ItemKind.GOAL)
    a = make_item(project, ItemKind.BATCH, parent_id=first_goal.id)
    b = make_item(project, ItemKind.BATCH, parent_id=first_goal.id)
    c = make_item(project, ItemKind.BATCH, parent_id=second_goal.id)
    s1 = make_item(project, ItemKind.SUBTASK, parent_id=b.id)
    s2 = make_item(project, ItemKind.SUBTASK, parent_id=b.id)
    s3 = make_item(project, ItemKind.SUBTASK, parent_id=c.id)
    assert [i.key for i in (first_goal, second_goal, a, b, c, s1, s2, s3)] == [
        "goal-1",
        "goal-2",
        "goal-1/batch-1",
        "goal-1/batch-2",
        "goal-2/batch-1",
        "goal-1/batch-2/subtask-1",
        "goal-1/batch-2/subtask-2",
        "goal-2/batch-1/subtask-1",
    ]
    assert [i.number for i in (s1, s2, s3)] == [1, 2, 1]


def test_backlog_has_its_own_counter(
    work_tree: tuple[Item, Item, Item, Item], capture_on: Callable[..., Item]
) -> None:
    """A batch numbers its backlog apart from its subtasks, and so does a goal."""
    goal, batch, first, _ = work_tree
    on_batch = [capture_on(first), capture_on(batch)]
    on_goal = capture_on(goal)
    assert [i.key for i in on_batch] == [
        "goal-1/batch-1/backlog-1",
        "goal-1/batch-1/backlog-2",
    ]
    assert on_goal.key == "goal-1/backlog-1"


def test_projects_number_independently(
    project: Project, other_project: Project, make_item: Callable[..., Item]
) -> None:
    """Every project starts at goal-1."""
    assert make_item(project, ItemKind.GOAL).key == "goal-1"
    assert make_item(other_project, ItemKind.GOAL).key == "goal-1"
    assert make_item(project, ItemKind.GOAL).key == "goal-2"


@pytest.mark.parametrize(
    ("kind", "parent"),
    [
        (ItemKind.GOAL, "goal"),
        (ItemKind.BATCH, None),
        (ItemKind.BATCH, "batch"),
        (ItemKind.SUBTASK, None),
        (ItemKind.SUBTASK, "goal"),
        (ItemKind.SUBTASK, "subtask"),
        (ItemKind.BACKLOG, "batch"),
    ],
)
# Each fixture the test needs is one argument.
def test_hierarchy_is_enforced(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    store: Store,
    project: Project,
    ctx: WriteContext,
    work_tree: tuple[Item, Item, Item, Item],
    kind: ItemKind,
    parent: str | None,
) -> None:
    """Every kind sits only where the model allows; backlog only via capture."""
    goal, batch, subtask, _ = work_tree
    parents = {"goal": goal, "batch": batch, "subtask": subtask}
    parent_id = None if parent is None else parents[parent].id
    with pytest.raises(HierarchyError):
        create_item(
            store,
            project.id,
            ItemCreate(kind=kind, title="t", parent_id=parent_id),
            ctx,
        )


def test_the_schema_refuses_a_key_that_breaks_the_path(
    store: Store, project: Project, work_tree: tuple[Item, Item, Item, Item]
) -> None:
    """A raw insert whose key does not extend its parent's key is refused."""
    _, batch, _, _ = work_tree
    with pytest.raises(Exception, match="does not match its parent"):
        with store.write() as conn:
            conn.execute(
                "INSERT INTO item (project_id, kind, number, key, parent_id, "
                "parent_kind, title, body, state, version, created_at, updated_at) "
                "VALUES (?, 'subtask', 9, 'goal-1/batch-9/subtask-9', ?, 'batch', "
                "'t', '', 'open', 1, '2026-09-29T00:00:00.000000Z', "
                "'2026-09-29T00:00:00.000000Z')",
                (project.id, batch.id),
            )
