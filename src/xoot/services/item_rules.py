"""
Item rules shared by every item write: the hierarchy, workflow states and
same-project references.
"""

import sqlite3

from xoot.exceptions.hierarchy_error import HierarchyError
from xoot.exceptions.state_error import StateError
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.category import TERMINAL_CATEGORIES, Category
from xoot.models.workflow.kind_workflow import KindWorkflow
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.services.lookups import require_decision, require_item

# The parent kinds each kind may have; None stands for the project itself.
PARENT_KINDS: dict[ItemKind, tuple[ItemKind | None, ...]] = {
    ItemKind.GOAL: (None,),
    ItemKind.BATCH: (ItemKind.GOAL,),
    ItemKind.SUBTASK: (ItemKind.BATCH,),
    ItemKind.BACKLOG: (ItemKind.BATCH, ItemKind.GOAL, None),
}
_WHERE = {
    ItemKind.GOAL: "a goal sits on the project and has no parent",
    ItemKind.BATCH: "a batch needs a parent goal",
    ItemKind.SUBTASK: "a subtask needs a parent batch",
    ItemKind.BACKLOG: "a backlog item sits on a batch, a goal or the project",
}


def check_parent(
    conn: sqlite3.Connection, project_id: int, kind: ItemKind, parent_id: int | None
) -> Item | None:
    """
    Enforce the hierarchy for a stored parent.

    The layering also rules out cycles: nothing sits under a subtask or a
    backlog item.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): the child's project.
        - kind (ItemKind): the child's kind.
        - parent_id (int | None): the proposed parent; None for the project.

    Returns:
        - parent (Item | None): the parent row, or None on the project.

    Raises:
        - HierarchyError: the parent is missing, forbidden or of the wrong kind.
        - NotFoundError: the parent does not exist.
        - CrossProjectError: the parent is in another project.
    """
    if parent_id is None:
        if None not in PARENT_KINDS[kind]:
            raise HierarchyError(_WHERE[kind])
        return None
    parent = require_item(conn, parent_id, project_id)
    check_child_kind(parent.kind, kind)
    return parent


def check_child_kind(parent_kind: ItemKind, kind: ItemKind) -> None:
    """
    Enforce the hierarchy for a parent that may not be stored yet, such as
    one planned earlier in the same bulk create.

    Args:
        - parent_kind (ItemKind): the parent's kind.
        - kind (ItemKind): the child's kind.

    Raises:
        - HierarchyError: the child kind may not sit under the parent kind.
    """
    if parent_kind not in PARENT_KINDS[kind]:
        raise HierarchyError(_WHERE[kind])


def check_state(workflow: KindWorkflow, state: str) -> Category:
    """
    Validate a state against the active workflow for the item's kind.

    Args:
        - workflow (KindWorkflow): the kind's active workflow.
        - state (str): the state to validate.

    Returns:
        - category (Category): the state's category.

    Raises:
        - StateError: the state is not in the workflow.
    """
    category = workflow.category_of(state)
    if category is None:
        raise StateError(f"state {state!r} is not in the active workflow")
    return category


def check_transition(workflow: KindWorkflow, source: str, target: str) -> None:
    """
    Enforce the workflow's allowed transitions for a user-requested move.

    Args:
        - workflow (KindWorkflow): the kind's active workflow.
        - source (str): current state.
        - target (str): requested state.

    Raises:
        - StateError: the transition is not allowed.
    """
    if not workflow.allows(source, target):
        raise StateError(f"transition {source!r} -> {target!r} is not allowed")


def check_awaited_decision(
    conn: sqlite3.Connection, project_id: int, decision_id: int | None
) -> None:
    """
    Check an item's awaited-decision reference.

    Args:
        - conn (sqlite3.Connection): open connection.
        - project_id (int): the item's project.
        - decision_id (int | None): referenced decision.

    Raises:
        - NotFoundError: the decision does not exist.
        - CrossProjectError: the decision is in another project.
    """
    if decision_id is not None:
        require_decision(conn, decision_id, project_id)


def category_of(definition: WorkflowDefinition, item: Item) -> Category | None:
    """
    Classify an item's state in a workflow.

    Args:
        - definition (WorkflowDefinition): the project's active workflow.
        - item (Item): the item.

    Returns:
        - category (Category | None): its category; None for a state the
          workflow no longer knows.
    """
    return definition.for_kind(item.kind).category_of(item.state)


def is_closed(definition: WorkflowDefinition, item: Item) -> bool:
    """
    Tell whether an item is done or dropped.

    Args:
        - definition (WorkflowDefinition): the project's active workflow.
        - item (Item): the item.

    Returns:
        - closed (bool): True in a terminal category.
    """
    return category_of(definition, item) in TERMINAL_CATEGORIES
