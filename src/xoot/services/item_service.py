"""
Creating, capturing and updating single items.

Numbers come from the project counter inside the write transaction, so
concurrent writers get unique, gap-free keys.
"""

from typing import Any

from xoot.models.event.actor import Actor
from xoot.models.event.entity_type import EntityType
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.workflow.category import Category
from xoot.models.workflow.kind_workflow import KindWorkflow
from xoot.services.conflicts import ensure_version
from xoot.services.id_checks import check_id
from xoot.services.item_rules import (
    check_parent,
    check_references,
    check_state,
    check_transition,
)
from xoot.services.item_writer import insert_item, write_item
from xoot.services.lookups import (
    active_workflow,
    require_item,
    require_project,
    require_session,
)
from xoot.services.session_links import (
    link_items,
    open_session_for,
    scope_session_id,
)
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store


def create_item(
    store: Store, project_id: int, request: ItemCreate, ctx: WriteContext
) -> Item:
    """
    Create a goal, batch or subtask.

    Args:
        - store (Store): the database.
        - project_id (int): project id.
        - request (ItemCreate): validated item details.
        - ctx (WriteContext): actor and optional session (linked if given).

    Returns:
        - item (Item): the new item.

    Raises:
        - HierarchyError: the parent is not allowed for this kind.
        - StateError: the state or session backlog breaks the workflow.
        - CrossProjectError: a reference is in another project.
        - SessionStateError: the session is closed.
        - InvalidIdError: project_id is not an int id.
        - NotFoundError: the project or a reference does not exist.
    """
    check_id("project_id", project_id)
    with store.write() as conn:
        return create_item_in(WriteScope(conn, ctx), project_id, request)


def create_item_in(scope: WriteScope, project_id: int, request: ItemCreate) -> Item:
    """
    Create a goal, batch or subtask; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope; its session, if any, is
          linked.
        - project_id (int): project id.
        - request (ItemCreate): validated item details.

    Returns:
        - item (Item): the new item.

    Raises:
        - HierarchyError: the parent is not allowed for this kind.
        - StateError: the state or session backlog breaks the workflow.
        - CrossProjectError: a reference is in another project.
        - SessionStateError: the session is closed.
        - NotFoundError: the project or a reference does not exist.
    """
    conn = scope.conn
    project = require_project(conn, project_id)
    session = open_session_for(conn, project_id, scope.ctx.session_id)
    workflow = active_workflow(conn, project).definition.for_kind(request.kind)
    check_parent(conn, project_id, request.kind, request.parent_id)
    state = request.state or workflow.default_state(Category.OPEN)
    check_state(workflow, state, request.backlog_session_id)
    check_references(
        conn, project_id, request.backlog_session_id, request.awaiting_decision_id
    )
    item = insert_item(scope, project, request.model_copy(update={"state": state}))
    link_items(scope, session, [item.id])
    return item


def capture(store: Store, session_id: int, draft: ItemDraft, actor: Actor) -> Item:
    """
    Capture a quick note as an unfiled subtask in the session's backlog.

    The subtask gets the default backlogged state and backlog_session_id set
    to this session, and is linked to the session.

    Args:
        - store (Store): the database.
        - session_id (int): an open session.
        - draft (ItemDraft): title and optional body.
        - actor (Actor): who captures it.

    Returns:
        - item (Item): the new unfiled subtask.

    Raises:
        - InvalidIdError: session_id is not an int id.
        - SessionStateError: the session is closed.
        - NotFoundError: no such session.
    """
    check_id("session_id", session_id)
    with store.write() as conn:
        scope = WriteScope(conn, WriteContext(actor=actor, session_id=session_id))
        return capture_in(scope, draft)


def capture_in(scope: WriteScope, draft: ItemDraft) -> Item:
    """
    Capture a quick note in the scope's session; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope, attributed to an open
          session.
        - draft (ItemDraft): title and optional body.

    Returns:
        - item (Item): the new unfiled subtask.

    Raises:
        - SessionStateError: the scope has no session, or it is closed.
        - NotFoundError: no such session.
    """
    conn = scope.conn
    session_id = scope_session_id(scope)
    project_id = require_session(conn, session_id).project_id
    session = open_session_for(conn, project_id, session_id)
    project = require_project(conn, project_id)
    workflow = active_workflow(conn, project).definition.for_kind(ItemKind.SUBTASK)
    request = ItemCreate(
        kind=ItemKind.SUBTASK,
        title=draft.title,
        body=draft.body,
        state=workflow.default_state(Category.BACKLOGGED),
        backlog_session_id=session_id,
    )
    item = insert_item(scope, project, request)
    link_items(scope, session, [item.id])
    return item


def update_item(
    store: Store,
    item_id: int,
    expected_version: int,
    changes: ItemUpdate,
    ctx: WriteContext,
) -> Item:
    """
    Change an item's title, body, state or references.

    Moving out of the backlogged category clears backlog_session_id unless
    the caller sets it (which then fails the backlog rule).

    Args:
        - store (Store): the database.
        - item_id (int): item id.
        - expected_version (int): the version the caller read.
        - changes (ItemUpdate): the fields to change.
        - ctx (WriteContext): actor and optional session (linked if given).

    Returns:
        - item (Item): the stored item.

    Raises:
        - VersionConflictError: the item changed since expected_version.
        - StateError: unknown state, disallowed transition or backlog rule.
        - CrossProjectError: a reference is in another project.
        - SessionStateError: the session is closed.
        - InvalidIdError: item_id or expected_version is not an int.
        - NotFoundError: the item or a reference does not exist.
    """
    check_id("item_id", item_id)
    check_id("expected_version", expected_version)
    with store.write() as conn:
        return update_item_in(WriteScope(conn, ctx), item_id, expected_version, changes)


def update_item_in(
    scope: WriteScope, item_id: int, expected_version: int, changes: ItemUpdate
) -> Item:
    """
    Change an item; the caller owns the transaction.

    Args:
        - scope (WriteScope): the open write scope; its session, if any, is
          linked.
        - item_id (int): item id.
        - expected_version (int): the version the caller read.
        - changes (ItemUpdate): the fields to change.

    Returns:
        - item (Item): the stored item.

    Raises:
        - VersionConflictError: the item changed since expected_version.
        - StateError: unknown state, disallowed transition or backlog rule.
        - CrossProjectError: a reference is in another project.
        - SessionStateError: the session is closed.
        - NotFoundError: the item or a reference does not exist.
    """
    conn = scope.conn
    item = require_item(conn, item_id)
    ensure_version(conn, EntityType.ITEM, item, expected_version)
    session = open_session_for(conn, item.project_id, scope.ctx.session_id)
    project = require_project(conn, item.project_id)
    workflow = active_workflow(conn, project).definition.for_kind(item.kind)
    fields = _effective_fields(item, workflow, changes)
    check_references(
        conn,
        item.project_id,
        fields.get("backlog_session_id"),
        fields.get("awaiting_decision_id"),
    )
    updated = write_item(scope, item, fields)
    link_items(scope, session, [item.id])
    return updated


def get_item(store: Store, item_id: int) -> Item:
    """
    Fetch an item.

    Args:
        - store (Store): the database.
        - item_id (int): item id.

    Returns:
        - item (Item): the item.

    Raises:
        - InvalidIdError: item_id is not an int id.
        - NotFoundError: no such item.
    """
    check_id("item_id", item_id)
    with store.read() as conn:
        return require_item(conn, item_id)


def _effective_fields(
    item: Item, workflow: KindWorkflow, changes: ItemUpdate
) -> dict[str, Any]:
    """Resolve the requested fields into the full set to write, validated."""
    fields = changes.provided()
    state = fields.get("state", item.state)
    if (
        "backlog_session_id" not in fields
        and item.backlog_session_id is not None
        and workflow.category_of(state) is not Category.BACKLOGGED
    ):
        fields["backlog_session_id"] = None
    check_state(
        workflow, state, fields.get("backlog_session_id", item.backlog_session_id)
    )
    check_transition(workflow, item.state, state)
    return fields
