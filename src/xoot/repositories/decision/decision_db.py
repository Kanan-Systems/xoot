"""SQL access for the decision table."""

import sqlite3

from xoot.exceptions.stale_write_error import StaleWriteError
from xoot.models.decision.decision import Decision
from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.decision.new_decision import NewDecision

_COLUMNS = (
    "id, project_id, number, key, title, body, status, supersedes_id, "
    "scope_item_id, version, created_at, updated_at"
)


def insert(conn: sqlite3.Connection, new: NewDecision) -> Decision:
    """
    Insert a decision at version 1.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - new (NewDecision): the validated row values.

    Returns:
        - decision (Decision): the stored row.
    """
    row = conn.execute(
        "INSERT INTO decision (project_id, number, key, title, body, status, "
        "supersedes_id, scope_item_id, version, created_at, updated_at) VALUES "
        "(:project_id, :number, :key, :title, :body, :status, :supersedes_id, "
        f":scope_item_id, 1, :created_at, :created_at) RETURNING {_COLUMNS}",
        new.model_dump(mode="json"),
    ).fetchone()
    return Decision.model_validate(dict(row))


def get(conn: sqlite3.Connection, decision_id: int) -> Decision | None:
    """
    Fetch a decision by id.

    Args:
        - conn (sqlite3.Connection): open connection.
        - decision_id (int): decision id.

    Returns:
        - decision (Decision | None): the row, or None.
    """
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM decision WHERE id = ?", (decision_id,)
    ).fetchone()
    return None if row is None else Decision.model_validate(dict(row))


def get_by_key(conn: sqlite3.Connection, key: str) -> Decision | None:
    """
    Fetch a decision by its public key.

    Args:
        - conn (sqlite3.Connection): open connection.
        - key (str): e.g. "xoot-D3".

    Returns:
        - decision (Decision | None): the decision, or None.
    """
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM decision WHERE key = ?", (key,)
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
        f"SELECT {_COLUMNS} FROM decision WHERE project_id = ? "
        "AND (? IS NULL OR status = ?) ORDER BY number DESC LIMIT ?",
        (project_id, value, value, limit),
    ).fetchall()
    return [Decision.model_validate(dict(row)) for row in rows]


def list_for_scope(
    conn: sqlite3.Connection, project_id: int, item_id: int, limit: int
) -> list[Decision]:
    """
    List the decisions scoped to one item, newest first.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): the item's project id.
        - item_id (int): the scope item id.
        - limit (int): the most rows to return.

    Returns:
        - decisions (list[Decision]): up to limit decisions.
    """
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM decision WHERE project_id = ? "
        "AND scope_item_id = ? ORDER BY number DESC LIMIT ?",
        (project_id, item_id, limit),
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
    params = decision.model_dump(mode="json")
    params["expected_version"] = expected_version
    cursor = conn.execute(
        "UPDATE decision SET title = :title, body = :body, status = :status, "
        "version = :version, updated_at = :updated_at "
        "WHERE id = :id AND version = :expected_version",
        params,
    )
    if cursor.rowcount != 1:
        raise StaleWriteError(f"decision {decision.id} changed during the transaction")
