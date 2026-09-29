"""
Storing item rows: numbering, keys, versions, aliases and events.

These are the raw writes under item_writer. They never run the completion
engine, which is why the engine itself writes through them; every other
caller goes through item_writer, which settles after each write.
"""

import sqlite3
from typing import Any

from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.new_item import NewItem
from xoot.models.project.project import Project
from xoot.repositories.item import item_alias_db, item_db
from xoot.repositories.project import project_db
from xoot.services.lookups import require_item, require_project
from xoot.services.write_scope import WriteScope
from xoot.utils.keys import child_key


def insert_row(scope: WriteScope, project: Project, request: ItemCreate) -> Item:
    """
    Allocate the item's number from its parent and store it with its event.

    The caller has already validated the request, including its state and
    parent. Goals and project-backlog items are numbered by the project;
    everything else by its parent (backlog items on their own counter).

    Args:
        - scope (WriteScope): the current write scope.
        - project (Project): the item's project.
        - request (ItemCreate): validated item details with state set.

    Returns:
        - item (Item): the stored item.
    """
    conn = scope.conn
    parent = (
        None if request.parent_id is None else require_item(conn, request.parent_id)
    )
    number = _allocate(scope, project, parent, request.kind)
    item = item_db.insert(
        conn,
        NewItem(
            project_id=project.id,
            kind=request.kind,
            number=number,
            key=child_key(None if parent is None else parent.key, request.kind, number),
            parent_id=request.parent_id,
            title=request.title,
            body=request.body,
            state=request.state,
            found_on_item_id=request.found_on_item_id,
            covered_by_item_id=None,
            origin_item_id=request.origin_item_id,
            awaiting_decision_id=request.awaiting_decision_id,
            created_at=scope.now,
        ),
    )
    scope.created(item)
    return item


def store_changes(scope: WriteScope, item: Item, fields: dict[str, Any]) -> Item:
    """
    Apply field changes to one item: validate, bump version, store, record.

    When the key changes (a move), the old key is recorded as an alias in
    the same transaction, so it keeps resolving to the item.

    Args:
        - scope (WriteScope): the current write scope.
        - item (Item): the current row.
        - fields (dict[str, Any]): field name to new value.

    Returns:
        - item (Item): the stored row (unchanged if nothing differed).

    Raises:
        - pydantic.ValidationError: a value breaks the item model.
        - StaleWriteError: the row changed inside the transaction.
    """
    candidate = merged(item, fields)
    if candidate == item:
        return item
    updated = candidate.model_copy(
        update={"version": item.version + 1, "updated_at": scope.now}
    )
    item_db.update(scope.conn, updated, item.version)
    if updated.key != item.key:
        item_alias_db.insert(scope.conn, item.project_id, item.key, item.id, scope.now)
    scope.updated(item, updated)
    return updated


def merged(item: Item, fields: dict[str, Any]) -> Item:
    """
    Build the row an item would become with some fields set.

    Args:
        - item (Item): the current row.
        - fields (dict[str, Any]): field name to new value.

    Returns:
        - item (Item): the validated candidate row.

    Raises:
        - pydantic.ValidationError: a value breaks the item model.
    """
    return Item.model_validate({**item.model_dump(), **fields})


def _allocate(
    scope: WriteScope, project: Project, parent: Item | None, kind: ItemKind
) -> int:
    """Take the item's number from the counter its parent keeps for its kind."""
    if parent is None:
        if kind is ItemKind.BACKLOG:
            return project_db.allocate_backlog_number(scope.conn, project.id)
        return project_db.allocate_goal_number(scope.conn, project.id)
    counter = "next_backlog_number" if kind is ItemKind.BACKLOG else "next_child_number"
    return item_db.allocate(scope.conn, parent.id, counter)


def peek_number(
    conn: sqlite3.Connection, project_id: int, parent: Item | None, kind: ItemKind
) -> int:
    """
    Read the number an insert of this kind would take, without taking it.

    Previews plan keys with it; the apply allocates for real and the plan
    digest catches any number another writer took in between.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): the project.
        - parent (Item | None): the parent; None on the project.
        - kind (ItemKind): the new item's kind.

    Returns:
        - number (int): the next number.
    """
    if parent is None:
        project = require_project(conn, project_id)
        if kind is ItemKind.BACKLOG:
            return project.next_backlog_number
        return project.next_goal_number
    counter = "next_backlog_number" if kind is ItemKind.BACKLOG else "next_child_number"
    return item_db.peek(conn, parent.id, counter)


def allocate_number(
    scope: WriteScope, project_id: int, parent: Item | None, kind: ItemKind
) -> int:
    """
    Take the number an item of this kind gets under a parent, for a move.

    Args:
        - scope (WriteScope): the current write scope.
        - project_id (int): the project.
        - parent (Item | None): the new parent; None on the project.
        - kind (ItemKind): the moving item's kind.

    Returns:
        - number (int): the allocated number.
    """
    return _allocate(scope, require_project(scope.conn, project_id), parent, kind)
