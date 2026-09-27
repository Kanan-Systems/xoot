"""
Describing what an op changed, for the plan and the result.

A diff of a stored row becomes PasteChange entries: states and statuses by
name, references by public key, and text fields by name only. Any other
field is named without values, so no stored text can reach a plan.
"""

import sqlite3
from typing import Any

from xoot.repositories.decision import decision_db
from xoot.repositories.item import item_db
from xoot.repositories.project import project_db
from xoot.repositories.session import session_db
from xoot.services.paste.models.paste_change import PasteChange
from xoot.utils.utils import session_key

_NAMED = frozenset({"state", "status"})
_REFERENCES = {
    "parent_id": "parent",
    "backlog_session_id": "backlog_session",
    "awaiting_decision_id": "awaiting_decision",
}
# Bookkeeping every write bumps; the version is reported per record instead.
_SKIPPED = frozenset({"version", "updated_at"})


def describe_changes(
    conn: sqlite3.Connection, key: str, before: dict[str, Any], after: dict[str, Any]
) -> tuple[PasteChange, ...]:
    """
    Turn one record's diff into plan entries.

    Args:
        - conn (sqlite3.Connection): a connection inside the paste's transaction.
        - key (str): the record's key.
        - before (dict[str, Any]): old values of the changed fields.
        - after (dict[str, Any]): new values of the changed fields.

    Returns:
        - changes (tuple[PasteChange, ...]): one entry per changed field,
          sorted by field name.
    """
    entries = []
    for name in sorted(after):
        if name in _SKIPPED:
            continue
        if name in _NAMED:
            entries.append(
                PasteChange(
                    key=key, field=name, before=before.get(name), after=after[name]
                )
            )
        elif name in _REFERENCES:
            entries.append(
                PasteChange(
                    key=key,
                    field=_REFERENCES[name],
                    before=_reference(conn, name, before.get(name)),
                    after=_reference(conn, name, after[name]),
                )
            )
        else:
            entries.append(PasteChange(key=key, field=name, before=None, after=None))
    return tuple(entries)


def session_key_of(conn: sqlite3.Connection, session_id: int | None) -> str | None:
    """
    Build a session's public key from its id.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - session_id (int | None): the session id.

    Returns:
        - key (str | None): e.g. "xoot-S3", or None for None or a missing row.
    """
    session = None if session_id is None else session_db.get(conn, session_id)
    if session is None:
        return None
    project = project_db.get(conn, session.project_id)
    return None if project is None else session_key(project.key_prefix, session.number)


def _reference(conn: sqlite3.Connection, name: str, row_id: int | None) -> str | None:
    """The public key behind a reference column's id."""
    if row_id is None:
        return None
    if name == "parent_id":
        item = item_db.get(conn, row_id)
        return None if item is None else item.key
    if name == "awaiting_decision_id":
        decision = decision_db.get(conn, row_id)
        return None if decision is None else decision.key
    return session_key_of(conn, row_id)
