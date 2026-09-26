"""F5: a write's session must be open and in the project; items get linked once."""

from collections.abc import Callable

import pytest

from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.exceptions.session_state_error import SessionStateError
from xoot.models.event.actor import Actor
from xoot.models.event.entity_type import EntityType
from xoot.models.event.event_action import EventAction
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.repositories.event import event_db
from xoot.repositories.session import session_item_ref_db
from xoot.services.session_close_service import close_session
from xoot.services.session_links import link_items, open_session_for
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store


def test_no_session_is_fine(store: Store, project: Project) -> None:
    """Writes outside a session skip the check."""
    with store.read() as conn:
        assert open_session_for(conn, project.id, None) is None


def test_session_must_be_open_and_local(
    store: Store,
    project: Project,
    other_project: Project,
    make_session: Callable[..., Session],
    user: Actor,
) -> None:
    """Another project's session, or a closed one, is refused."""
    session = make_session(project)
    with store.read() as conn:
        assert open_session_for(conn, project.id, session.id) == session
        with pytest.raises(CrossProjectError):
            open_session_for(conn, other_project.id, session.id)
    close_session(store, session.id, SessionClose(), user)
    with store.read() as conn:
        with pytest.raises(SessionStateError):
            open_session_for(conn, project.id, session.id)


def test_items_are_linked_once(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
    ctx: WriteContext,
) -> None:
    """Re-linking an already linked item writes no row and no event."""
    item, session = make_item(project, ItemKind.GOAL), make_session(project)
    for _ in range(2):
        with store.write() as conn:
            link_items(WriteScope(conn, ctx), session, [item.id])
    with store.read() as conn:
        events = event_db.list_for_entity(conn, EntityType.SESSION, session.id)
        refs = session_item_ref_db.list_for_session(conn, session.id)
    assert [(e.action, e.after) for e in events][1:] == [
        (EventAction.LINK, {"item_id": item.id})
    ]
    assert [ref.item_id for ref in refs] == [item.id]
