"""
Starting and reading sessions.

Starting a session links its focus items and reports what earlier sessions
left in their backlogs, so work parked at a close is offered again.
"""

from xoot.models.event.actor import Actor
from xoot.models.event.write_context import WriteContext
from xoot.models.session.focus_warning import FocusWarning
from xoot.models.session.new_session import NewSession
from xoot.models.session.session import Session
from xoot.models.session.session_start import SessionStart
from xoot.models.session.session_start_result import SessionStartResult
from xoot.repositories.item import item_db
from xoot.repositories.project import project_db
from xoot.repositories.session import session_db, session_item_ref_db
from xoot.services.id_checks import check_id
from xoot.services.lookups import require_item, require_project, require_session
from xoot.services.session_links import link_items
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store


def start_session(
    store: Store, project_id: int, request: SessionStart, actor: Actor
) -> SessionStartResult:
    """
    Open a session and link its focus items.

    A focus item already linked to another open session is allowed and
    reported as a warning, not rejected.

    Args:
        - store (Store): the database.
        - project_id (int): project id.
        - request (SessionStart): title and focus items.
        - actor (Actor): who starts it; actor.client becomes the session's
          client.

    Returns:
        - result (SessionStartResult): the session, pending session-backlog
          items from closed sessions, and focus warnings.

    Raises:
        - InvalidIdError: project_id is not an int id.
        - NotFoundError: the project or a focus item does not exist.
        - CrossProjectError: a focus item is in another project.
    """
    check_id("project_id", project_id)
    with store.write() as conn:
        return start_session_in(
            WriteScope(conn, WriteContext(actor=actor)), project_id, request
        )


def start_session_in(
    scope: WriteScope, project_id: int, request: SessionStart
) -> SessionStartResult:
    """
    Open a session and link its focus items; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope, attributed to no
          session; its actor's client becomes the session's client.
        - project_id (int): project id.
        - request (SessionStart): title and focus items.

    Returns:
        - result (SessionStartResult): the session, pending session-backlog
          items from closed sessions, and focus warnings.

    Raises:
        - NotFoundError: the project or a focus item does not exist.
        - CrossProjectError: a focus item is in another project.
    """
    conn = scope.conn
    require_project(conn, project_id)
    focus = [
        require_item(conn, item_id, project_id) for item_id in request.focus_item_ids
    ]
    warnings = []
    for item in focus:
        others = session_item_ref_db.open_session_ids(conn, item.id)
        if others:
            warnings.append(
                FocusWarning(
                    item_id=item.id, key=item.key, open_session_ids=tuple(others)
                )
            )
    session = session_db.insert(
        conn,
        NewSession(
            project_id=project_id,
            number=session_db.next_number(conn, project_id),
            client=scope.ctx.actor.client,
            title=request.title,
            start_seq=project_db.allocate_seq(conn, project_id),
            started_at=scope.now,
        ),
    )
    scope = scope.with_session(session.id)
    scope.created(session)
    link_items(scope, session, [item.id for item in focus])
    pending = item_db.list_session_backlogged(conn, project_id, None)
    return SessionStartResult(
        session=session, pending=tuple(pending), warnings=tuple(warnings)
    )


def get_session(store: Store, session_id: int) -> Session:
    """
    Fetch a session.

    Args:
        - store (Store): the database.
        - session_id (int): session id.

    Returns:
        - session (Session): the session.

    Raises:
        - InvalidIdError: session_id is not an int id.
        - NotFoundError: no such session.
    """
    check_id("session_id", session_id)
    with store.read() as conn:
        return require_session(conn, session_id)
