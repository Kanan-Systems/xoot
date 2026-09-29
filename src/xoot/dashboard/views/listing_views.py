"""Project lists: sessions, one session, backlogs and decisions."""

import sqlite3

from xoot.dashboard.schemas.backlog_row import BacklogRow
from xoot.dashboard.schemas.backlogs_view import BacklogsView
from xoot.dashboard.schemas.decisions_view import DecisionsView
from xoot.dashboard.schemas.session_backlog_entry import SessionBacklogEntry
from xoot.dashboard.schemas.session_item_entry import SessionItemEntry
from xoot.dashboard.schemas.session_row import SessionRow
from xoot.dashboard.schemas.session_view import SessionView
from xoot.dashboard.schemas.sessions_view import SessionsView
from xoot.dashboard.views.lookup import project_of, session_in
from xoot.models.fields import format_timestamp
from xoot.models.item.item import Item
from xoot.models.session.session_status import SessionStatus
from xoot.repositories.decision import decision_db
from xoot.server.key_book import KeyBook
from xoot.server.render import decision_summary, item_summary, session_summary
from xoot.services.backlog_service import backlog_items, session_backlogs
from xoot.services.session_reads import (
    linked_counts,
    list_sessions,
    session_items,
    session_links,
)

SESSIONS_MAX = 200
BACKLOG_MAX = 100
# High enough that the tree's decision badges count every decision of a
# typical project; truncated says when they may not.
DECISIONS_MAX = 500


def sessions_view(
    conn: sqlite3.Connection, prefix: str, status: SessionStatus | None
) -> SessionsView:
    """
    List a project's sessions, open first, then newest first.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the project prefix from the path.
        - status (SessionStatus | None): only this status; any when None.

    Returns:
        - view (SessionsView): up to SESSIONS_MAX sessions.

    Raises:
        - ApiError: 404, no such project.
    """
    project = project_of(conn, prefix)
    book = KeyBook(conn)
    # One row past the cap tells whether the list was cut.
    rows = list_sessions(conn, project.id, status, SESSIONS_MAX + 1)
    counts = linked_counts(conn, project.id)
    return SessionsView(
        project=project.key_prefix,
        sessions=[
            SessionRow(
                **session_summary(book, s).model_dump(),
                linked_items=counts.get(s.id, 0),
            )
            for s in rows[:SESSIONS_MAX]
        ],
        truncated=len(rows) > SESSIONS_MAX,
    )


def session_view(conn: sqlite3.Connection, prefix: str, key: str) -> SessionView:
    """
    Return one session of the project with its linked items.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the project prefix from the path.
        - key (str): the session key from the path.

    Returns:
        - view (SessionView): the session, its summary, the linked item keys
          and each linked item with its disposition.

    Raises:
        - ApiError: 404, no such project, or no such session in it.
    """
    session = session_in(conn, project_of(conn, prefix), key)
    book = KeyBook(conn)
    return SessionView(
        session=session_summary(book, session),
        summary=session.summary,
        items=session_items(conn, session.id),
        linked=[
            SessionItemEntry(
                item=item_summary(book, link.item),
                disposition=link.disposition,
                captured=link.captured,
            )
            for link in session_links(conn, session.id)
        ],
    )


def backlogs_view(conn: sqlite3.Connection, prefix: str) -> BacklogsView:
    """
    Return every backlog of a project: per open session, project, unfiled.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the project prefix from the path.

    Returns:
        - view (BacklogsView): each list capped at BACKLOG_MAX.

    Raises:
        - ApiError: 404, no such project.
    """
    project = project_of(conn, prefix)
    book = KeyBook(conn)
    project_items = backlog_items(conn, project.id, "project")
    unfiled = backlog_items(conn, project.id, "unfiled")
    return BacklogsView(
        project=project.key_prefix,
        sessions=[
            SessionBacklogEntry(
                session=session_summary(book, entry.session),
                items=_capped(book, list(entry.items)),
                truncated=len(entry.items) > BACKLOG_MAX,
            )
            for entry in session_backlogs(conn, project.id)
        ],
        project_backlog=_capped(book, project_items),
        project_backlog_truncated=len(project_items) > BACKLOG_MAX,
        unfiled=_capped(book, unfiled),
        unfiled_truncated=len(unfiled) > BACKLOG_MAX,
    )


def decisions_view(conn: sqlite3.Connection, prefix: str) -> DecisionsView:
    """
    List a project's decisions, newest first.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - prefix (str): the project prefix from the path.

    Returns:
        - view (DecisionsView): up to DECISIONS_MAX decisions.

    Raises:
        - ApiError: 404, no such project.
    """
    project = project_of(conn, prefix)
    book = KeyBook(conn)
    rows = decision_db.list_recent(conn, project.id, None, DECISIONS_MAX + 1)
    return DecisionsView(
        project=project.key_prefix,
        decisions=[decision_summary(book, d) for d in rows[:DECISIONS_MAX]],
        truncated=len(rows) > DECISIONS_MAX,
    )


def _capped(book: KeyBook, items: list[Item]) -> list[BacklogRow]:
    return [
        BacklogRow(
            **item_summary(book, item).model_dump(),
            created_at=format_timestamp(item.created_at),
        )
        for item in items[:BACKLOG_MAX]
    ]
