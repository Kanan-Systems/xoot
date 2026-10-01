"""
The backlog list as backlog_list returns it, shared by the MCP tool and
`xoot backlog`, so both show the same items, order, cap and shape.
"""

import sqlite3

from xoot.models.item.item import Item
from xoot.models.project.project import Project
from xoot.server.key_book import KeyBook
from xoot.server.render import item_summary
from xoot.server.schemas.backlog_entry import BacklogEntry
from xoot.server.schemas.backlog_output import BacklogOutput
from xoot.server.schemas.literals import ResolvedBy
from xoot.services.backlog_reads import backlog_items, backlog_level

BACKLOG_MAX = 100


def backlog_output(
    conn: sqlite3.Connection,
    project: Project,
    resolved_by: ResolvedBy,
    target: Item | None,
    include_closed: bool,
) -> BacklogOutput:
    """
    List a project's backlog, or one goal's or batch's, capped.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project (Project): the resolved project.
        - resolved_by (ResolvedBy): how the project was found.
        - target (Item | None): the goal or batch asked for; None for all.
        - include_closed (bool): also list done and dropped items.

    Returns:
        - output (BacklogOutput): project level first, then by key, at most
          BACKLOG_MAX items, and whether the cap hid any.

    Raises:
        - NotFoundError: the project or its workflow is missing.
    """
    book = KeyBook(conn)
    items = backlog_items(conn, project.id, target, include_closed)
    return BacklogOutput(
        project=project.key_prefix,
        resolved_by=resolved_by,
        at=None if target is None else target.key,
        items=[
            BacklogEntry(
                **item_summary(book, item).model_dump(),
                level=backlog_level(item),
                found_on=book.item_key(item.found_on_item_id),
            )
            for item in items[:BACKLOG_MAX]
        ],
        truncated=len(items) > BACKLOG_MAX,
    )
