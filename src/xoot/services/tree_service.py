"""
The bounded tree query.

Walks the hierarchy breadth-first so a small item budget shows every goal
before any subtask, then returns the nodes in pre-order for display.
"""

import sqlite3

from xoot.models.item.item import Item
from xoot.models.item.tree_node import TreeNode
from xoot.models.item.tree_query import TreeQuery
from xoot.models.item.tree_result import TreeResult
from xoot.models.workflow.category import TERMINAL_CATEGORIES
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.repositories.item import item_db
from xoot.services.id_checks import check_id
from xoot.services.lookups import active_workflow, require_item, require_project
from xoot.store.store import Store


def tree(store: Store, project_id: int, query: TreeQuery) -> TreeResult:
    """
    Return part of a project's item tree within the query's bounds.

    An explicitly requested root is always included, even if done or
    dropped. Items hidden by the terminal filter hide their subtree.

    Args:
        - store (Store): the database.
        - project_id (int): project id.
        - query (TreeQuery): root, depth, item budget and terminal filter.

    Returns:
        - result (TreeResult): nodes in pre-order and a truncated flag.

    Raises:
        - InvalidIdError: project_id is not an int id.
        - NotFoundError: the project or the root does not exist.
        - CrossProjectError: the root is in another project.
    """
    check_id("project_id", project_id)
    with store.read() as conn:
        return tree_in(conn, project_id, query)


def tree_in(conn: sqlite3.Connection, project_id: int, query: TreeQuery) -> TreeResult:
    """
    Return part of a project's item tree inside the caller's transaction.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project_id (int): project id.
        - query (TreeQuery): root, depth, item budget and terminal filter.

    Returns:
        - result (TreeResult): nodes in pre-order and a truncated flag.

    Raises:
        - InvalidIdError: project_id is not an int id.
        - NotFoundError: the project or the root does not exist.
        - CrossProjectError: the root is in another project.
    """
    check_id("project_id", project_id)
    definition = active_workflow(conn, require_project(conn, project_id)).definition
    if query.root_id is not None:
        roots = [require_item(conn, query.root_id, project_id)]
    else:
        roots = [
            i
            for i in item_db.list_roots(conn, project_id)
            if _shown(definition, query, i)
        ]
    return _walk(conn, definition, query, roots)


def _walk(
    conn: sqlite3.Connection,
    definition: WorkflowDefinition,
    query: TreeQuery,
    roots: list[Item],
) -> TreeResult:
    """Breadth-first walk within the depth and item budget."""
    truncated = len(roots) > query.max_items
    level = roots[: query.max_items]
    children: dict[int, list[Item]] = {}
    count = len(level)
    for _ in range(query.depth):
        below = _shown_children(conn, definition, query, level)
        if len(below) > query.max_items - count:
            truncated = True
            below = below[: query.max_items - count]
        for item in below:
            children.setdefault(item.parent_id or 0, []).append(item)
        count += len(below)
        level = below
        if not level:
            break
    else:
        # Depth limit reached: anything still below the last level is hidden.
        truncated = truncated or bool(_shown_children(conn, definition, query, level))
    nodes: list[TreeNode] = []
    for root in roots[: query.max_items]:
        _pre_order(root, 0, children, nodes)
    return TreeResult(nodes=tuple(nodes), truncated=truncated)


def _shown_children(
    conn: sqlite3.Connection,
    definition: WorkflowDefinition,
    query: TreeQuery,
    level: list[Item],
) -> list[Item]:
    if not level:
        return []
    project_id = level[0].project_id
    below = item_db.list_children(conn, project_id, [item.id for item in level])
    return [item for item in below if _shown(definition, query, item)]


def _shown(definition: WorkflowDefinition, query: TreeQuery, item: Item) -> bool:
    if query.include_terminal:
        return True
    category = definition.for_kind(item.kind).category_of(item.state)
    return category not in TERMINAL_CATEGORIES


def _pre_order(
    item: Item, depth: int, children: dict[int, list[Item]], nodes: list[TreeNode]
) -> None:
    nodes.append(TreeNode(item=item, depth=depth, unfiled=item.unfiled))
    for child in children.get(item.id, []):
        _pre_order(child, depth + 1, children, nodes)
