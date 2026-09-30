"""
Choosing an item update's path: a direct update, a subtree drop or a reparent.

The item_update tool and paste mode both choose here, so they apply the same
rules and translate keys to ids the same way. A parent change goes through
the subtree reparent, and a drop of an item with children through the
subtree drop. Either must come alone: combining it with other fields would
need two transactions.
"""

import sqlite3
from collections.abc import Callable, Set
from typing import Any, Literal

from xoot.exceptions.update_path_error import UpdatePathError
from xoot.models.item.item import Item
from xoot.models.item.item_changes_input import ItemChangesInput
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.workflow.category import Category
from xoot.repositories.item import item_db
from xoot.services.lookups import active_workflow, require_project

type UpdatePath = Literal["update", "drop", "reparent"]

ALONE = "{} must be the only change; send the other changes in a separate update"
BACKLOG_PARENT = "backlog items move with backlog_push or backlog_cover"


def has_children(conn: sqlite3.Connection, item: Item) -> bool:
    """
    Tell whether an item has any child.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - item (Item): the item.

    Returns:
        - has_children (bool): True when at least one item names it as parent.
    """
    return bool(item_db.list_children(conn, item.project_id, [item.id]))


def drops(conn: sqlite3.Connection, item: Item, state: str | None) -> bool:
    """
    Tell whether moving an item to a state puts it in the dropped category.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - item (Item): the item.
        - state (str | None): the requested state; None never drops.

    Returns:
        - drops (bool): True for a state of the dropped category.

    Raises:
        - NotFoundError: the project or its workflow is missing.
    """
    if state is None:
        return False
    workflow = active_workflow(conn, require_project(conn, item.project_id))
    return workflow.definition.for_kind(item.kind).category_of(state) is (
        Category.DROPPED
    )


def choose_path(
    conn: sqlite3.Connection, item: Item, provided: Set[str], state: str | None
) -> tuple[UpdatePath, bool]:
    """
    Pick the path for a set of changed fields.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - item (Item): the item being changed.
        - provided (Set[str]): the public names of the fields the caller set.
        - state (str | None): the requested state, if any.

    Returns:
        - path (tuple[UpdatePath, bool]): the path, and whether the item has
          children.

    Raises:
        - UpdatePathError: a parent change, or a drop of an item with
          children, was combined with other fields, or a backlog item was
          given a parent.
        - NotFoundError: the project or its workflow is missing.
    """
    children = has_children(conn, item)
    if "parent" in provided:
        if item.kind is ItemKind.BACKLOG:
            raise UpdatePathError(BACKLOG_PARENT)
        if provided != {"parent"}:
            raise UpdatePathError(ALONE.format("parent"))
        return "reparent", children
    if children and drops(conn, item, state):
        if provided != {"state"}:
            raise UpdatePathError(ALONE.format("a drop of an item with children"))
        return "drop", children
    return "update", children


def item_update_from(
    changes: ItemChangesInput, decision_id: Callable[[str], int]
) -> ItemUpdate:
    """
    Translate key-based changes into the service's id-based update.

    Each caller resolves keys its own way (the tool raises a ToolError, paste
    also accepts refs), so the lookup is passed in.

    Args:
        - changes (ItemChangesInput): the changes, on the direct update path.
        - decision_id (Callable[[str], int]): decision key to id.

    Returns:
        - update (ItemUpdate): the same changes with ids.

    Raises:
        - pydantic.ValidationError: a field breaks the update model.
    """
    fields: dict[str, Any] = {}
    for name in changes.model_fields_set:
        value = getattr(changes, name)
        if name == "awaiting_decision":
            fields["awaiting_decision_id"] = (
                None if value is None else decision_id(value)
            )
        else:
            fields[name] = value
    return ItemUpdate(**fields)
