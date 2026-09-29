"""
Changes xoot derives on its own (completion, reopening, workflow remaps) are
recorded as the system's, with the triggering write's client.
"""

from collections.abc import Callable

from xoot.models.event.actor import Actor
from xoot.models.event.entity_type import EntityType
from xoot.models.event.event import Event
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.workflow.category import Category
from xoot.models.workflow.kind_workflow import REQUIRED_DEFAULTS, KindWorkflow
from xoot.models.workflow.state_spec import StateSpec
from xoot.models.workflow.workflow_change import WorkflowChange
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.repositories.event import event_db
from xoot.services.item_service import update_item
from xoot.services.workflow_service import set_workflow
from xoot.store.store import Store


def _project_events(store: Store, project: Project) -> list[Event]:
    with store.read() as conn:
        return event_db.list_for_project(conn, project.id)


def _who(event: Event) -> tuple[str, str]:
    return (event.actor_kind.value, event.client.value)


def test_completion_is_logged_as_system(
    store: Store,
    project: Project,
    claude: Actor,
    make_item: Callable[..., Item],
) -> None:
    """The caller's own update is theirs; the batch and goal completions are not."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    subtask = make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
    seen = len(_project_events(store, project))
    update_item(
        store, subtask.id, 1, ItemUpdate(state="done"), WriteContext(actor=claude)
    )
    updates = [
        (e.entity_id, *_who(e))
        for e in _project_events(store, project)[seen:]
        if e.entity_type is EntityType.ITEM
    ]
    assert updates == [
        (subtask.id, "claude", "code"),
        (batch.id, "system", "code"),
        (goal.id, "system", "code"),
    ]


def test_workflow_remaps_are_logged_as_system(
    store: Store,
    project: Project,
    claude: Actor,
    make_item: Callable[..., Item],
) -> None:
    """The workflow change is the caller's; each remapped item is the system's."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    blocked = make_item(project, ItemKind.SUBTASK, parent_id=batch.id, state="blocked")
    subtask = KindWorkflow(
        states=tuple(
            StateSpec(name=c.value, category=c)
            for c in Category
            if c.value != "blocked"
        ),
        defaults={c: c.value for c in REQUIRED_DEFAULTS},
    )
    kinds = dict(WorkflowDefinition.default().kinds) | {ItemKind.SUBTASK: subtask}
    change = WorkflowChange(
        definition=WorkflowDefinition(kinds=kinds),
        mapping={ItemKind.SUBTASK: {"blocked": "active"}},
    )
    seen = len(_project_events(store, project))
    set_workflow(store, project.id, change, WriteContext(actor=claude))
    events = _project_events(store, project)[seen:]
    assert [(e.entity_type.value, e.action.value, *_who(e)) for e in events] == [
        ("workflow", "create", "claude", "code"),
        ("project", "update", "claude", "code"),
        ("item", "update", "system", "code"),
    ]
    assert events[2].entity_id == blocked.id
