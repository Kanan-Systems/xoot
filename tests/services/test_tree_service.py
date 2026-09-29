"""The tree query is bounded by root, depth and item count."""

from collections.abc import Callable

import pytest

from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.tree_query import TreeQuery
from xoot.models.project.project import Project
from xoot.services.backlog_push_service import apply_push
from xoot.services.tree_service import tree
from xoot.store.store import Store


@pytest.fixture(name="items")
# Each fixture is one argument: the tree is built from all of them.
def fixture_items(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    store: Store,
    project: Project,
    ctx: WriteContext,
    make_item: Callable[..., Item],
    capture_on: Callable[..., Item],
    set_state: Callable[..., Item],
) -> dict[str, Item]:
    """
    g1 > b1 > (s1 open, s2 done);  g2 (dropped) > b2;  u1 on the project.
    """
    g1 = make_item(project, ItemKind.GOAL)
    b1 = make_item(project, ItemKind.BATCH, parent_id=g1.id)
    s1 = make_item(project, ItemKind.SUBTASK, parent_id=b1.id)
    s2 = make_item(project, ItemKind.SUBTASK, parent_id=b1.id, state="done")
    g2 = make_item(project, ItemKind.GOAL)
    b2 = make_item(project, ItemKind.BATCH, parent_id=g2.id)
    g2 = set_state(g2, "dropped")
    u1 = capture_on(g1)
    apply_push(store, u1.id, ctx, None)
    return {"g1": g1, "b1": b1, "s1": s1, "s2": s2, "g2": g2, "b2": b2, "u1": u1}


def _shape(
    store: Store, project: Project, items: dict[str, Item], **query: object
) -> tuple[list[tuple[str, int]], bool]:
    names = {item.id: name for name, item in items.items()}
    result = tree(store, project.id, TreeQuery.model_validate(query))
    return [(names[n.item.id], n.depth) for n in result.nodes], result.truncated


def test_default_hides_done_and_dropped(
    store: Store, project: Project, items: dict[str, Item]
) -> None:
    """Terminal items and their subtrees are left out; order is pre-order."""
    nodes, truncated = _shape(store, project, items)
    assert nodes == [("g1", 0), ("b1", 1), ("s1", 2), ("u1", 0)]
    assert truncated is False


def test_include_terminal(
    store: Store, project: Project, items: dict[str, Item]
) -> None:
    """Asked for, done and dropped items are shown with their subtrees."""
    nodes, _ = _shape(store, project, items, include_terminal=True)
    assert [name for name, _ in nodes] == ["g1", "b1", "s1", "s2", "g2", "b2", "u1"]


def test_depth_bound_truncates(
    store: Store, project: Project, items: dict[str, Item]
) -> None:
    """Hidden levels are reported as truncation."""
    assert _shape(store, project, items, depth=1) == (
        [("g1", 0), ("b1", 1), ("u1", 0)],
        True,
    )
    assert _shape(store, project, items, depth=2)[1] is False


def test_item_bound_truncates_breadth_first(
    store: Store, project: Project, items: dict[str, Item]
) -> None:
    """A small budget shows top-level items before any deeper ones."""
    assert _shape(store, project, items, max_items=2) == ([("g1", 0), ("u1", 0)], True)
    assert _shape(store, project, items, max_items=4)[1] is False


def test_root_bound(store: Store, project: Project, items: dict[str, Item]) -> None:
    """With a root only its subtree is returned; an explicit root is always shown."""
    assert _shape(store, project, items, root_id=items["b1"].id) == (
        [("b1", 0), ("s1", 1)],
        False,
    )
    assert _shape(store, project, items, root_id=items["g2"].id)[0] == [
        ("g2", 0),
        ("b2", 1),
    ]


def test_project_backlog_follows_the_goals(
    store: Store, project: Project, items: dict[str, Item]
) -> None:
    """Project-level backlog items are roots, listed after every goal."""
    result = tree(store, project.id, TreeQuery(depth=0))
    assert [n.item.key for n in result.nodes] == ["goal-1", "backlog-1"]
    assert result.nodes[-1].item.id == items["u1"].id
