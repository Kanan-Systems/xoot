"""Session links with their dispositions and captures, and per-session counts."""

from collections.abc import Callable

from xoot.models.event.actor import Actor
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.session.disposition import Disposition
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.services.item_service import capture, create_item, update_item
from xoot.services.session_close_service import close_session
from xoot.services.session_reads import linked_counts, session_links
from xoot.store.store import Store


def test_links_carry_disposition_and_capture_flag(
    store: Store,
    user: Actor,
    project: Project,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
) -> None:
    """Open items get the close's disposition; a done item none; captures flagged."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    session = make_session(project, goal.id)
    in_session = WriteContext(actor=user, session_id=session.id)
    update_item(store, batch.id, 1, ItemUpdate(state="done"), in_session)
    held = capture(store, session.id, ItemDraft(title="held"), user)
    with store.read() as conn:
        before = session_links(conn, session.id)
    assert [(link.item.key, link.disposition, link.captured) for link in before] == [
        (goal.key, None, False),
        (batch.key, None, False),
        (held.key, None, True),
    ]
    close_session(
        store,
        session.id,
        SessionClose(
            dispositions={
                goal.id: Disposition.CARRY_OVER,
                held.id: Disposition.SESSION_BACKLOG,
            }
        ),
        user,
    )
    with store.read() as conn:
        after = {link.item.key: link for link in session_links(conn, session.id)}
    assert after[goal.key].disposition is Disposition.CARRY_OVER
    assert after[batch.key].disposition is None
    assert after[batch.key].item.state == "done"
    assert after[held.key].disposition is Disposition.SESSION_BACKLOG
    assert after[held.key].captured is True


def test_an_unfiled_create_outside_the_backlog_is_not_a_capture(
    store: Store,
    user: Actor,
    project: Project,
    make_session: Callable[..., Session],
) -> None:
    """Created in the session, but not into its backlog: not captured."""
    session = make_session(project)
    created = create_item(
        store,
        project.id,
        ItemCreate(kind=ItemKind.SUBTASK, title="plain"),
        WriteContext(actor=user, session_id=session.id),
    )
    with store.read() as conn:
        links = session_links(conn, session.id)
    assert [(link.item.key, link.captured) for link in links] == [(created.key, False)]


def test_linked_counts_per_session(
    store: Store,
    project: Project,
    other_project: Project,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
) -> None:
    """Counts per session of the project; a session with no links is absent."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    two = make_session(project, goal.id, batch.id)
    empty = make_session(other_project)
    with store.read() as conn:
        counts = linked_counts(conn, project.id)
        other = linked_counts(conn, other_project.id)
    assert counts == {two.id: 2}
    assert empty.id not in other
