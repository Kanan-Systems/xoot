"""
Describing what an op changed, for the plan and the result.

A diff of a stored row becomes PasteChange entries: states, statuses and a
moved item's key by value, references by public key, and text fields by
name only. Any other
field is named without values, so no stored text can reach a plan.
"""

import sqlite3
from typing import Any

from xoot.repositories.decision import decision_db
from xoot.repositories.item import item_db
from xoot.services.paste.models.paste_change import PasteChange

_NAMED = frozenset({"state", "status"})
_REFERENCES = {
    "parent_id": "parent",
    "awaiting_decision_id": "awaiting_decision",
    "covered_by_item_id": "covered_by",
}
# A move's new key and number are reported as the key change alone.
_KEYS = frozenset({"key"})
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
        if name == "number":
            continue
        if name in _NAMED or name in _KEYS:
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


def _reference(conn: sqlite3.Connection, name: str, row_id: int | None) -> str | None:
    """The public key behind a reference column's id."""
    if row_id is None:
        return None
    if name == "awaiting_decision_id":
        decision = decision_db.get(conn, row_id)
        return None if decision is None else decision.key
    item = item_db.get(conn, row_id)
    return None if item is None else item.key
