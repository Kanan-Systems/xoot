"""
Workflow versions: reading the active one and replacing it.

A change adds a version, activates it and remaps affected items in the same
transaction, so no item is ever left in a state its workflow does not know.
"""

import sqlite3
from typing import Any

from xoot.exceptions.workflow_mapping_error import WorkflowMappingError
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.workflow.category import Category
from xoot.models.workflow.workflow import Workflow
from xoot.models.workflow.workflow_change import WorkflowChange
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.repositories.item import item_db
from xoot.repositories.project import project_db
from xoot.repositories.workflow import workflow_db
from xoot.services.item_writer import write_item
from xoot.services.lookups import active_workflow, require_project
from xoot.services.session_links import link_items, open_session_for
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store


def get_active_workflow(store: Store, project_id: int) -> Workflow:
    """
    Fetch the workflow version a project currently uses.

    Args:
        - store (Store): the database.
        - project_id (int): project id.

    Returns:
        - workflow (Workflow): the active version.

    Raises:
        - NotFoundError: no such project.
    """
    with store.read() as conn:
        return active_workflow(conn, require_project(conn, project_id))


def set_workflow(
    store: Store, project_id: int, change: WorkflowChange, ctx: WriteContext
) -> Workflow:
    """
    Add and activate a new workflow version, remapping affected items.

    Items in a state the new definition removes move to the state the
    mapping names; items whose state leaves the backlogged category lose
    their session backlog. Each item change is its own event.

    Args:
        - store (Store): the database.
        - project_id (int): project id.
        - change (WorkflowChange): the new definition and state mapping.
        - ctx (WriteContext): actor and optional session.

    Returns:
        - workflow (Workflow): the new active version.

    Raises:
        - WorkflowMappingError: an in-use removed state is not mapped, or
          the mapping names a state the change does not remove.
        - NotFoundError: no such project.
    """
    with store.write() as conn:
        project = require_project(conn, project_id)
        session = open_session_for(conn, project_id, ctx.session_id)
        _check_mapping_keys(active_workflow(conn, project).definition, change)
        remaps = _plan_remaps(conn, project_id, change)
        scope = WriteScope(conn, ctx)
        version = workflow_db.next_version(conn, project_id)
        workflow = workflow_db.insert(
            conn, project_id, version, change.definition, scope.now
        )
        scope.created(workflow)
        scope.updated(
            project, project_db.set_active_workflow(conn, project_id, workflow.id)
        )
        for item, fields in remaps:
            write_item(scope, item, fields)
        link_items(scope, session, [item.id for item, _ in remaps])
        return workflow


def _check_mapping_keys(current: WorkflowDefinition, change: WorkflowChange) -> None:
    """Only states that exist today and are removed by the change may be mapped."""
    for kind, moves in change.mapping.items():
        old, new = current.for_kind(kind), change.definition.for_kind(kind)
        for source in moves:
            if old.category_of(source) is None or new.category_of(source) is not None:
                raise WorkflowMappingError(
                    f"{kind} mapping may only name states this change removes: {source!r}"
                )


def _plan_remaps(
    conn: sqlite3.Connection, project_id: int, change: WorkflowChange
) -> list[tuple[Item, dict[str, Any]]]:
    """Plan every item change the new definition forces, or refuse the change."""
    uncovered: dict[str, int] = {}
    planned: list[tuple[Item, dict[str, Any]]] = []
    for item in item_db.list_for_project(conn, project_id):
        workflow = change.definition.for_kind(item.kind)
        state: str | None = item.state
        if workflow.category_of(item.state) is None:
            state = change.mapping.get(item.kind, {}).get(item.state)
        if state is None:
            label = f"{item.kind}:{item.state}"
            uncovered[label] = uncovered.get(label, 0) + 1
            continue
        fields: dict[str, Any] = {}
        if state != item.state:
            fields["state"] = state
        if (
            item.backlog_session_id is not None
            and workflow.category_of(state) is not Category.BACKLOGGED
        ):
            fields["backlog_session_id"] = None
        if fields:
            planned.append((item, fields))
    if uncovered:
        detail = ", ".join(
            f"{label} ({count})" for label, count in sorted(uncovered.items())
        )
        raise WorkflowMappingError(
            f"items use removed states with no mapping: {detail}"
        )
    return planned
