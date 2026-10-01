"""SQL access for the workflow table."""

import json
import sqlite3
from datetime import datetime
from typing import Any

from xoot.models.fields import format_timestamp
from xoot.models.workflow.workflow import Workflow
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.repositories.stored_row import from_row

_COLUMNS = "id, project_id, version, definition, created_at"


def insert(
    conn: sqlite3.Connection,
    project_id: int,
    version: int,
    definition: WorkflowDefinition,
    created_at: datetime,
) -> Workflow:
    """
    Store a workflow version.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - project_id (int): project id.
        - version (int): the next version number for the project.
        - definition (WorkflowDefinition): validated definition.
        - created_at (datetime): creation time.

    Returns:
        - workflow (Workflow): the stored row.
    """
    row = conn.execute(
        f"INSERT INTO workflow (project_id, version, definition, created_at) "
        f"VALUES (?, ?, ?, ?) RETURNING {_COLUMNS}",
        (
            project_id,
            version,
            json.dumps(definition.model_dump(mode="json"), sort_keys=True),
            format_timestamp(created_at),
        ),
    ).fetchone()
    return _to_workflow(row)


def get(conn: sqlite3.Connection, workflow_id: int) -> Workflow | None:
    """
    Fetch a workflow version by id.

    Args:
        - conn (sqlite3.Connection): open connection.
        - workflow_id (int): workflow id.

    Returns:
        - workflow (Workflow | None): the row, or None.
    """
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM workflow WHERE id = ?", (workflow_id,)
    ).fetchone()
    return None if row is None else _to_workflow(row)


def next_version(conn: sqlite3.Connection, project_id: int) -> int:
    """
    Return the version number the next workflow of a project gets.

    Args:
        - conn (sqlite3.Connection): connection inside a write transaction.
        - project_id (int): project id.

    Returns:
        - version (int): one past the highest stored version.
    """
    row = conn.execute(
        "SELECT coalesce(max(version), 0) + 1 FROM workflow WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    return int(row[0])


def _to_workflow(row: sqlite3.Row) -> Workflow:
    values: dict[str, Any] = dict(row)
    values["definition"] = json.loads(values["definition"])
    return from_row(Workflow, "workflow", values)
