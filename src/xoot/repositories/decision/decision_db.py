"""
SQL access for the decision table.

A decision's key is not stored: every read joins the owner item and builds
"<owner key>/decision-<number>", so the key follows the owner when it moves.
"""

import sqlite3

from xoot.exceptions.stale_write_error import StaleWriteError
from xoot.models.decision.decision import Decision
from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.decision.new_decision import NewDecision

_SELECT = (
    "SELECT decision.id, decision.project_id, decision.owner_item_id, "
    "decision.number, item.key || '/decision-' || decision.number AS key, "
    "decision.title, decision.body, decision.status, decision.supersedes_id, "
    "decision.version, decision.created_at, decision.updated_at "
    "FROM decision JOIN item ON item.id = decision.owner_item_id"
)


def insert(conn: sqlite3.Connection, new: NewDecision) -> Decision:
    """
    Insert a decision at version 1.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - new (NewDecision): the validated row values.

    Returns:
        - decision (Decision): the stored row, with its derived key.
    """
    row = conn.execute(
        "INSERT INTO decision (project_id, owner_item_id, owner_kind, number, "
        "title, body, status, supersedes_id, version, created_at, updated_at) "
        "SELECT :project_id, :owner_item_id, kind, :number, :title, :body, "
        ":status, :supersedes_id, 1, :created_at, :created_at FROM item "
        "WHERE id = :owner_item_id RETURNING id",
        new.model_dump(mode="json"),
    ).fetchone()
    decision = get(conn, int(row[0]))
    if decision is None:
        raise StaleWriteError("a decision vanished inside its own transaction")
    return decision


def get(conn: sqlite3.Connection, decision_id: int) -> Decision | None:
    """
    Fetch a decision by id.

    Args:
        - conn (sqlite3.Connection): open connection.
        - decision_id (int): decision id.

    Returns:
        - decision (Decision | None): the row, or None.
    """
    row = conn.execute(f"{_SELECT} WHERE decision.id = ?", (decision_id,)).fetchone()
    return None if row is None else Decision.model_validate(dict(row))


def get_by_owner(
    conn: sqlite3.Connection, owner_item_id: int, number: int
) -> Decision | None:
    """
    Fetch a decision by its owner and number.

    Args:
        - conn (sqlite3.Connection): open connection.
        - owner_item_id (int): the owner item id.
        - number (int): the decision number on that owner.

    Returns:
        - decision (Decision | None): the row, or None.
    """
    row = conn.execute(
        f"{_SELECT} WHERE decision.owner_item_id = ? AND decision.number = ?",
        (owner_item_id, number),
    ).fetchone()
    return None if row is None else Decision.model_validate(dict(row))


def list_recent(
    conn: sqlite3.Connection,
    project_id: int,
    status: DecisionStatus | None,
    limit: int,
) -> list[Decision]:
    """
    List a project's decisions, newest first.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): project id.
        - status (DecisionStatus | None): only this status; any when None.
        - limit (int): the most rows to return.

    Returns:
        - decisions (list[Decision]): up to limit decisions.
    """
    value = None if status is None else status.value
    rows = conn.execute(
        f"{_SELECT} WHERE decision.project_id = ? "
        "AND (? IS NULL OR decision.status = ?) ORDER BY decision.id DESC LIMIT ?",
        (project_id, value, value, limit),
    ).fetchall()
    return [Decision.model_validate(dict(row)) for row in rows]


def list_for_owner(
    conn: sqlite3.Connection, owner_item_id: int, limit: int
) -> list[Decision]:
    """
    List the decisions made on one item, newest first.

    Args:
        - conn (sqlite3.Connection): open connection.
        - owner_item_id (int): the owner item id.
        - limit (int): the most rows to return.

    Returns:
        - decisions (list[Decision]): up to limit decisions.
    """
    rows = conn.execute(
        f"{_SELECT} WHERE decision.owner_item_id = ? "
        "ORDER BY decision.number DESC LIMIT ?",
        (owner_item_id, limit),
    ).fetchall()
    return [Decision.model_validate(dict(row)) for row in rows]


def update(conn: sqlite3.Connection, decision: Decision, expected_version: int) -> None:
    """
    Write a decision's mutable columns, guarded by its previous version.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - decision (Decision): the new row values, version already bumped.
        - expected_version (int): the version being replaced.

    Raises:
        - StaleWriteError: no row had that id and version.
    """
    cursor = conn.execute(
        "UPDATE decision SET title = ?, body = ?, status = ?, version = ?, "
        "updated_at = ? WHERE id = ? AND version = ?",
        (
            decision.title,
            decision.body,
            decision.status.value,
            decision.version,
            decision.model_dump(mode="json")["updated_at"],
            decision.id,
            expected_version,
        ),
    )
    if cursor.rowcount != 1:
        raise StaleWriteError(f"decision {decision.id} changed during the transaction")
