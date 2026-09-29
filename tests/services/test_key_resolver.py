"""Public keys resolve to rows within a project, raising XootErrors."""

from collections.abc import Callable

import pytest

from xoot.exceptions.not_found_error import NotFoundError
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.event.entity_type import EntityType
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services import key_resolver
from xoot.services.decision_service import create_decision
from xoot.store.store import Store


def test_every_kind_of_key(
    store: Store,
    project: Project,
    ctx: WriteContext,
    work_tree: tuple[Item, Item, Item, Item],
    capture_on: Callable[..., Item],
) -> None:
    """Items at every depth, backlog items, decisions and prefixes resolve."""
    goal, batch, first, _ = work_tree
    backlog = capture_on(first)
    decision = create_decision(
        store, project.id, DecisionCreate(owner_item_id=batch.id, title="d"), ctx
    )
    with store.read() as conn:
        for item in (goal, batch, first, backlog):
            assert key_resolver.item_by_key(conn, project.id, item.key).id == item.id
        assert decision.key == "goal-1/batch-1/decision-1"
        found = key_resolver.decision_by_key(conn, project.id, decision.key)
        assert found.id == decision.id
        assert key_resolver.project_by_key(conn, "xoot").id == project.id
        resolved = [
            key_resolver.entity_by_key(conn, project.id, key)
            for key in ("goal-1/batch-1/subtask-1", "goal-1/batch-1/decision-1")
        ]
    assert resolved == [
        (EntityType.ITEM, first.id),
        (EntityType.DECISION, decision.id),
    ]


@pytest.mark.parametrize(
    ("key", "ref"),
    [
        ("goal-99", "goal-99"),
        ("goal-1/decision-7", "goal-1/decision-7"),
        ("NOT A KEY\x1b[2J", "malformed key"),
        ("xoot-1", "malformed key"),
        ("goal-1/subtask-1", "malformed key"),
    ],
)
@pytest.mark.usefixtures("work_tree")
def test_unknown_keys_do_not_echo_input(
    store: Store, project: Project, key: str, ref: str
) -> None:
    """Only a well-formed key is kept on the error."""
    with store.read() as conn:
        with pytest.raises(NotFoundError) as caught:
            key_resolver.entity_by_key(conn, project.id, key)
    assert caught.value.ref == ref


def test_keys_are_per_project(
    store: Store,
    project: Project,
    other_project: Project,
    make_item: Callable[..., Item],
) -> None:
    """goal-1 of one project is not goal-1 of another."""
    mine = make_item(project, ItemKind.GOAL)
    theirs = make_item(other_project, ItemKind.GOAL)
    assert mine.key == theirs.key == "goal-1"
    with store.read() as conn:
        assert key_resolver.item_by_key(conn, project.id, "goal-1").id == mine.id
        found = key_resolver.item_by_key(conn, other_project.id, "goal-1")
    assert found.id == theirs.id
