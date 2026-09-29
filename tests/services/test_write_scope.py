"""Every mutation writes its event rows, in the same transaction."""

from collections.abc import Callable

import pytest

from xoot.exceptions.state_error import StateError
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.decision.decision_update import DecisionUpdate
from xoot.models.event.actor import Actor
from xoot.models.event.entity_type import EntityType
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.workflow.workflow_change import WorkflowChange
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.repositories.event import event_db
from xoot.services.backlog_push_service import apply_push
from xoot.services.backlog_service import capture, cover
from xoot.services.decision_service import create_decision, update_decision
from xoot.services.item_service import create_item, update_item
from xoot.services.project_service import add_alias, add_path
from xoot.services.subtree_service import apply_drop, apply_reparent
from xoot.services.workflow_service import set_workflow
from xoot.services.write_scope import changed_fields
from xoot.store.store import Store

type Kinds = list[tuple[str, str]]


@pytest.fixture(name="fresh")
def fixture_fresh(
    event_kinds: Callable[[Project], Kinds],
) -> Callable[[Project], Kinds]:
    """Factory: the events a project gained since the previous call."""
    seen: dict[int, int] = {}

    def new_since_last(project: Project) -> Kinds:
        kinds = event_kinds(project)
        start, seen[project.id] = seen.get(project.id, 0), len(kinds)
        return kinds[start:]

    return new_since_last


def test_project_workflow_and_item_mutations(
    store: Store,
    project: Project,
    ctx: WriteContext,
    fresh: Callable[[Project], Kinds],
    extended_definition: WorkflowDefinition,
) -> None:
    """Registration, naming, item writes, subtree applies and workflow changes."""
    assert fresh(project) == [
        ("project", "create"),
        ("workflow", "create"),
        ("project", "add_alias"),
        ("project", "add_path"),
    ]
    add_alias(store, project.id, "xoot-alt", ctx)
    add_path(store, project.id, "/srv/xoot", ctx)
    assert fresh(project) == [("project", "add_alias"), ("project", "add_path")]
    goal, _ = create_item(
        store, project.id, ItemCreate(kind=ItemKind.GOAL, title="g"), ctx
    )
    update_item(store, goal.id, 1, ItemUpdate(title="renamed"), ctx)
    assert fresh(project) == [("item", "create"), ("item", "update")]
    batch, _ = create_item(
        store,
        project.id,
        ItemCreate(kind=ItemKind.BATCH, title="b", parent_id=goal.id),
        ctx,
    )
    other, _ = create_item(
        store, project.id, ItemCreate(kind=ItemKind.GOAL, title="g2"), ctx
    )
    apply_reparent(store, batch.id, other.id, 1, ctx)
    apply_drop(store, batch.id, 2, ctx)
    # The move, the drop, and the system dropping goal-2, now all dropped.
    assert fresh(project) == [
        ("item", "create"),
        ("item", "create"),
        ("item", "update"),
        ("item", "update"),
        ("item", "update"),
    ]
    change = WorkflowChange(definition=extended_definition)
    set_workflow(store, project.id, change, ctx)
    assert fresh(project) == [("workflow", "create"), ("project", "update")]


def test_backlog_mutations(
    store: Store,
    project: Project,
    ctx: WriteContext,
    work_tree: tuple[Item, Item, Item, Item],
    fresh: Callable[[Project], Kinds],
) -> None:
    """Capture, push (one update, the alias rides along) and cover."""
    goal, _, first, _ = work_tree
    fresh(project)
    note, _ = capture(store, project.id, first.id, ItemDraft(title="note"), ctx)
    assert fresh(project) == [("item", "create")]
    apply_push(store, note.id, ctx, None)
    assert fresh(project) == [("item", "update")]
    cover(store, note.id, work_tree[1].id, ctx)
    assert fresh(project) == [("item", "create"), ("item", "update")]
    del goal


def test_decision_mutations(
    store: Store, project: Project, ctx: WriteContext, fresh: Callable[[Project], Kinds]
) -> None:
    """Create, supersede (two rows) and update."""
    goal, _ = create_item(
        store, project.id, ItemCreate(kind=ItemKind.GOAL, title="g"), ctx
    )
    fresh(project)
    old = create_decision(
        store, project.id, DecisionCreate(owner_item_id=goal.id, title="d1"), ctx
    )
    assert fresh(project) == [("decision", "create")]
    request = DecisionCreate(owner_item_id=goal.id, title="d2", supersedes_id=old.id)
    create_decision(store, project.id, request, ctx)
    assert fresh(project) == [("decision", "create"), ("decision", "update")]
    update_decision(store, old.id, 2, DecisionUpdate(body="why"), ctx)
    assert fresh(project) == [("decision", "update")]


def test_events_carry_actor_and_diff(
    store: Store, project: Project, make_item: Callable[..., Item], claude: Actor
) -> None:
    """An update event records who, through which client, and only what changed."""
    goal = make_item(project, ItemKind.GOAL)
    ctx = WriteContext(actor=claude)
    update_item(store, goal.id, 1, ItemUpdate(state="active"), ctx)
    with store.read() as conn:
        event = event_db.list_for_entity(conn, EntityType.ITEM, goal.id)[-1]
    assert (event.actor_kind, event.client) == (claude.kind, claude.client)
    assert event.before == {"state": "open", "version": 1}
    assert event.after == {"state": "active", "version": 2}


def test_failed_write_leaves_no_event(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    ctx: WriteContext,
    event_kinds: Callable[[Project], Kinds],
) -> None:
    """A rejected write rolls back, so no event describes it."""
    goal = make_item(project, ItemKind.GOAL)
    before = event_kinds(project)
    with pytest.raises(StateError):
        update_item(store, goal.id, 1, ItemUpdate(state="someday"), ctx)
    assert event_kinds(project) == before


def test_changed_fields_ignores_updated_at(
    project: Project, make_item: Callable[..., Item]
) -> None:
    """updated_at is the event's own timestamp, so diffs leave it out."""
    goal = make_item(project, ItemKind.GOAL)
    moved = goal.model_copy(update={"title": "new", "updated_at": goal.created_at.max})
    assert changed_fields(goal, moved) == ({"title": "goal item"}, {"title": "new"})
