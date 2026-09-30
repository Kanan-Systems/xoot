"""
The completion engine: the one place goals and batches complete and reopen.

insert_item and write_item call settle() after every item write. It walks
up from the written item: a subtask or backlog item settles its batch (then
that batch's goal) or its goal; a batch settles its goal. A move settles
both the old and the new parent.

A goal or batch with work under it completes once every child (subtasks for
a batch, batches for a goal) is done or dropped and no open backlog item
sits on it: it moves to its default done state, or its default dropped
state when every child was dropped. Open backlog holds it open; the write's
report lists it as blocked. One with no children never completes. A closed
goal or batch that gains open work (a new or reopened child, a captured or
pushed backlog item) moves back to its default open state. Every such write
is the system's, in the same transaction, and lands in the scope's log.

Completion is the engine's alone: check_manual_done refuses a requested
done state on a goal or batch while open work or open backlog sits on it.
"""

import sqlite3
from collections.abc import Iterable

from xoot.exceptions.open_children_error import OpenChildrenError
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.category import Category
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.repositories.item import item_db
from xoot.services.item_rules import category_of, is_closed
from xoot.services.item_store import store_changes
from xoot.services.lookups import active_workflow, require_item, require_project
from xoot.services.write_scope import WriteScope

_CHILD_KIND = {ItemKind.GOAL: ItemKind.BATCH, ItemKind.BATCH: ItemKind.SUBTASK}


def settle(scope: WriteScope, item: Item, previous: Item | None = None) -> None:
    """
    Complete or reopen every goal and batch above a written item.

    Args:
        - scope (WriteScope): the write's scope; its log gets the outcomes.
        - item (Item): the item as just stored.
        - previous (Item | None): the item before the write; None for an
          insert. Its parent is settled too when the item moved.
    """
    if item.kind is ItemKind.GOAL:
        return
    definition = active_workflow(
        scope.conn, require_project(scope.conn, item.project_id)
    ).definition
    parents = [item.parent_id]
    if previous is not None and previous.parent_id != item.parent_id:
        parents.insert(0, previous.parent_id)
    for container in _containers(scope, parents):
        if container.id not in scope.held:
            _evaluate(scope, definition, container)


def check_manual_done(
    conn: sqlite3.Connection, definition: WorkflowDefinition, item: Item, state: str
) -> None:
    """
    Refuse a requested done state on a goal or batch that still has open work.

    Args:
        - conn (sqlite3.Connection): a connection inside the write.
        - definition (WorkflowDefinition): the project's active workflow.
        - item (Item): the item being updated.
        - state (str): the state the caller asked for.

    Raises:
        - OpenChildrenError: a child work item or a backlog item on it is
          neither done nor dropped; the error lists their keys.
    """
    if item.kind not in _CHILD_KIND:
        return
    if definition.for_kind(item.kind).category_of(state) is not Category.DONE:
        return
    open_keys = [
        child.key
        for kind in (_CHILD_KIND[item.kind], ItemKind.BACKLOG)
        for child in item_db.list_children_of_kind(conn, item.id, kind)
        if not is_closed(definition, child)
    ]
    if open_keys:
        raise OpenChildrenError(item.key, open_keys)


def _containers(scope: WriteScope, parent_ids: Iterable[int | None]) -> list[Item]:
    """Each parent and, for a batch, its goal; bottom up, without repeats."""
    chain: list[Item] = []
    for parent_id in parent_ids:
        if parent_id is None:
            continue
        parent = require_item(scope.conn, parent_id)
        chain.append(parent)
        if parent.kind is ItemKind.BATCH and parent.parent_id is not None:
            chain.append(require_item(scope.conn, parent.parent_id))
    unique: dict[int, Item] = {}
    for container in chain:
        unique.setdefault(container.id, container)
    return list(unique.values())


def _evaluate(
    scope: WriteScope, definition: WorkflowDefinition, container: Item
) -> None:
    """Complete, reopen, or report one goal or batch as blocked."""
    # Re-read: an earlier step of this settle may have just written it.
    current = require_item(scope.conn, container.id)
    children = item_db.list_children_of_kind(
        scope.conn, current.id, _CHILD_KIND[current.kind]
    )
    open_work = [c for c in children if not is_closed(definition, c)]
    open_backlog = sum(
        1
        for b in item_db.list_children_of_kind(scope.conn, current.id, ItemKind.BACKLOG)
        if not is_closed(definition, b)
    )
    workflow = definition.for_kind(current.kind)
    if is_closed(definition, current):
        if open_work or open_backlog:
            _move(scope, current, workflow.default_state(Category.OPEN))
            scope.log.record(current.key, "reopened")
        return
    if not children or open_work:
        scope.log.unblock(current.key)
        return
    if open_backlog:
        scope.log.block(current.key, open_backlog)
        return
    all_dropped = all(category_of(definition, c) is Category.DROPPED for c in children)
    target = Category.DROPPED if all_dropped else Category.DONE
    _move(scope, current, workflow.default_state(target))
    scope.log.record(current.key, "completed")


def _move(scope: WriteScope, item: Item, state: str) -> None:
    """Write a state change as the system, without settling again."""
    store_changes(scope.as_system(), item, {"state": state})
