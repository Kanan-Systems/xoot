"""
Plan digests cover every column an apply writes, not only keys and states.

Each plan type is previewed twice with one difference that leaves every
state alone: a parent, or the key a move would hand out. The digests must
differ.
"""

from collections.abc import Callable

import pytest

from xoot.models.confirm.plan_entry import PlanEntry
from xoot.models.event.write_context import WriteContext
from xoot.models.item.bulk_create import BulkCreate
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services.backlog_push_service import preview_push
from xoot.services.bulk_service import preview_bulk
from xoot.services.confirm_service import plan_digest
from xoot.services.subtree_service import apply_reparent, preview_drop, preview_reparent
from xoot.store.store import Store

ENTRY = PlanEntry(
    key="goal-1/batch-1/subtask-1",
    kind=ItemKind.SUBTASK,
    title="t",
    body_sha256="0" * 64,
    state="open",
    parent_key="goal-1/batch-1",
    awaiting_decision_key=None,
)


def test_digest_ignores_entry_order() -> None:
    """The same entries in another order give the same digest."""
    other = ENTRY.model_copy(update={"key": "goal-1/batch-1/subtask-2"})
    assert plan_digest([ENTRY, other]) == plan_digest([other, ENTRY])


@pytest.mark.parametrize(
    "field, value",
    [
        ("key", "goal-2/batch-1/subtask-1"),
        ("kind", ItemKind.BATCH),
        ("title", "u"),
        ("body_sha256", "1" * 64),
        ("state", "dropped"),
        ("parent_key", "goal-2/batch-1"),
        ("awaiting_decision_key", "goal-1/decision-1"),
    ],
)
def test_digest_changes_with_every_field(field: str, value: object) -> None:
    """Changing any one column of one entry changes the digest."""
    assert plan_digest([ENTRY]) != plan_digest(
        [ENTRY.model_copy(update={field: value})]
    )


def test_bulk_digest_pins_the_parent(
    store: Store, project: Project, make_item: Callable[..., Item]
) -> None:
    """The same new batch under two different goals plans two digests."""
    first = make_item(project, ItemKind.GOAL)
    second = make_item(project, ItemKind.GOAL)

    def digest(parent: Item) -> str:
        request = BulkCreate.model_validate(
            {"items": [{"kind": "batch", "title": "b", "parent_id": parent.id}]}
        )
        return preview_bulk(store, project.id, request).plan_sha256

    assert digest(first) != digest(second)


def test_drop_digest_pins_the_parent(
    store: Store,
    project: Project,
    ctx: WriteContext,
    make_item: Callable[..., Item],
) -> None:
    """Dropping the same batch after it moved to another goal plans a new digest."""
    first = make_item(project, ItemKind.GOAL)
    second = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=first.id)
    before = preview_drop(store, batch.id).plan_sha256
    apply_reparent(store, batch.id, second.id, batch.version, ctx)
    assert preview_drop(store, batch.id).plan_sha256 != before


def test_reparent_digest_pins_the_new_parent(
    store: Store, project: Project, make_item: Callable[..., Item]
) -> None:
    """Moving the same batch under two different goals plans two digests."""
    home = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=home.id)
    first = make_item(project, ItemKind.GOAL)
    second = make_item(project, ItemKind.GOAL)
    assert (
        preview_reparent(store, batch.id, first.id).plan_sha256
        != preview_reparent(store, batch.id, second.id).plan_sha256
    )


def test_push_digest_pins_the_new_key(
    store: Store,
    work_tree: tuple[Item, Item, Item, Item],
    capture_on: Callable[..., Item],
) -> None:
    """A number taken on the goal since the preview changes the push's plan."""
    goal, _, first, _ = work_tree
    item = capture_on(first)
    before = preview_push(store, item.id).plan_sha256
    capture_on(goal)
    assert preview_push(store, item.id).plan_sha256 != before
