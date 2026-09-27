"""
X6: changes xoot derives on its own (F9 backlog moves, workflow remaps) are
recorded as the system's, with the triggering write's client and session.
"""

from collections.abc import Callable

from xoot.models.event.actor import Actor
from xoot.models.event.entity_type import EntityType
from xoot.models.event.event import Event
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.session.disposition import Disposition
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.models.workflow.category import Category
from xoot.models.workflow.kind_workflow import KindWorkflow
from xoot.models.workflow.state_spec import StateSpec
from xoot.models.workflow.workflow_change import WorkflowChange
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.repositories.event import event_db
from xoot.services.item_service import capture
from xoot.services.session_close_service import close_session
from xoot.services.workflow_service import set_workflow
from xoot.store.store import Store


def _project_events(store: Store, project: Project) -> list[Event]:
    with store.read() as conn:
        return event_db.list_for_project(conn, project.id)


def _who(event: Event) -> tuple[str, str, int | None]:
    return (event.actor_kind.value, event.client.value, event.session_id)


def test_f9_moves_are_logged_as_system(
    store: Store,
    project: Project,
    claude: Actor,
    make_session: Callable[..., Session],
    make_item: Callable[..., Item],
) -> None:
    """The closer's own disposition is theirs; the F9 move is the system's."""
    early = make_session(project)
    parked = capture(store, early.id, ItemDraft(title="parked"), claude)
    close_session(
        store,
        early.id,
        SessionClose(dispositions={parked.id: Disposition.SESSION_BACKLOG}),
        claude,
    )
    focus = make_item(project, ItemKind.SUBTASK)
    current = make_session(project, focus.id)
    seen = len(_project_events(store, project))
    close_session(
        store,
        current.id,
        SessionClose(dispositions={focus.id: Disposition.DROPPED}),
        claude,
    )
    item_updates = {
        e.entity_id: _who(e)
        for e in _project_events(store, project)[seen:]
        if e.entity_type is EntityType.ITEM
    }
    assert item_updates == {
        focus.id: ("claude", "code", current.id),
        parked.id: ("system", "code", current.id),
    }


def test_workflow_remaps_are_logged_as_system(
    store: Store,
    project: Project,
    claude: Actor,
    make_session: Callable[..., Session],
    make_item: Callable[..., Item],
) -> None:
    """The workflow change is the caller's; each remapped item is the system's."""
    blocked = make_item(project, ItemKind.SUBTASK, state="blocked")
    session = make_session(project)
    subtask = KindWorkflow(
        states=tuple(
            StateSpec(name=c.value, category=c)
            for c in Category
            if c.value != "blocked"
        ),
        defaults={
            c: c.value for c in (Category.OPEN, Category.BACKLOGGED, Category.DROPPED)
        },
    )
    kinds = dict(WorkflowDefinition.default().kinds) | {ItemKind.SUBTASK: subtask}
    change = WorkflowChange(
        definition=WorkflowDefinition(kinds=kinds),
        mapping={ItemKind.SUBTASK: {"blocked": "active"}},
    )
    seen = len(_project_events(store, project))
    set_workflow(
        store, project.id, change, WriteContext(actor=claude, session_id=session.id)
    )
    events = _project_events(store, project)[seen:]
    assert [(e.entity_type.value, e.action.value, *_who(e)) for e in events] == [
        ("workflow", "create", "claude", "code", session.id),
        ("project", "update", "claude", "code", session.id),
        ("item", "update", "system", "code", session.id),
        ("session", "link", "claude", "code", session.id),
    ]
    assert events[2].entity_id == blocked.id
