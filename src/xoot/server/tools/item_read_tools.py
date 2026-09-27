"""Item read tools: tree_get, item_get and backlog_list."""

from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from xoot.models.event.entity_type import EntityType
from xoot.models.item.item import Item
from xoot.models.item.tree_query import MAX_DEPTH, MAX_ITEMS, TreeQuery
from xoot.models.workflow.category import TERMINAL_CATEGORIES, Category
from xoot.repositories.event import event_db
from xoot.repositories.item import item_db
from xoot.server.db_call import run_db
from xoot.server.key_book import KeyBook
from xoot.server.render import event_entry, item_detail, item_summary
from xoot.server.resolution import item_by_key, optional_item_id, resolve_project
from xoot.server.roots import root_paths
from xoot.server.schemas.arguments import ItemKey, ProjectAlias
from xoot.server.schemas.backlog_output import BacklogOutput
from xoot.server.schemas.children_summary import ChildrenSummary
from xoot.server.schemas.item_get_output import ItemGetOutput
from xoot.server.schemas.literals import BacklogScope
from xoot.server.schemas.tree_entry import TreeEntry
from xoot.server.schemas.tree_output import TreeOutput
from xoot.server.tool_meta import READ, RESOLUTION, describe
from xoot.services.tree_service import tree
from xoot.store.store import Store

RECENT_EVENTS = 10
CHILDREN_MAX = 25
BACKLOG_MAX = 100


# One parameter per tool argument: the SDK derives the input schema from it.
async def tree_get(  # pylint: disable=too-many-arguments
    ctx: Context,
    project: ProjectAlias = None,
    *,
    root: Annotated[
        str | None, Field(description="Item key to start from; goals when omitted.")
    ] = None,
    depth: Annotated[int, Field(ge=0, le=MAX_DEPTH)] = 3,
    include_done: Annotated[
        bool, Field(description="Also show done and dropped items.")
    ] = False,
    limit: Annotated[int, Field(ge=1, le=MAX_ITEMS)] = 200,
) -> TreeOutput:
    """
    Return part of a project's item tree.

    Args:
        - ctx (Context): the request context.
        - project (str | None): an alias; resolved from roots or cwd if None.
        - root (str | None): the item key to start from.
        - depth (int): levels below the roots.
        - include_done (bool): include done and dropped items.
        - limit (int): the most items to return.

    Returns:
        - output (TreeOutput): nodes in pre-order and a truncated flag.
    """
    roots = await root_paths(ctx, project)

    def work(store: Store) -> TreeOutput:
        found, resolved_by = resolve_project(store, project, roots)
        with store.read() as conn:
            root_id = optional_item_id(conn, root)
        query = TreeQuery(
            root_id=root_id,
            depth=depth,
            max_items=limit,
            include_terminal=include_done,
        )
        result = tree(store, found.id, query)
        with store.read() as conn:
            book = KeyBook(conn)
            nodes = [
                TreeEntry(
                    depth=node.depth,
                    unfiled=node.unfiled,
                    item=item_summary(book, node.item),
                )
                for node in result.nodes
            ]
        return TreeOutput(
            project=found.key_prefix,
            resolved_by=resolved_by,
            nodes=nodes,
            truncated=result.truncated,
        )

    return await run_db(ctx, work)


async def item_get(ctx: Context, key: ItemKey) -> ItemGetOutput:
    """
    Return one item with its children and recent events.

    Args:
        - ctx (Context): the request context.
        - key (str): the item key.

    Returns:
        - output (ItemGetOutput): the item, children summary and events.
    """

    def work(store: Store) -> ItemGetOutput:
        with store.read() as conn:
            book = KeyBook(conn)
            item = item_by_key(conn, key)
            children = item_db.list_children(conn, item.project_id, [item.id])
            events = event_db.list_for_entity(conn, EntityType.ITEM, item.id)
            return ItemGetOutput(
                item=item_detail(book, item),
                children=_children(book, children),
                events=[event_entry(book, e) for e in events[::-1][:RECENT_EVENTS]],
            )

    return await run_db(ctx, work)


async def backlog_list(
    ctx: Context,
    scope: Annotated[
        BacklogScope,
        Field(
            description=(
                "session: parked in a session's backlog; project: in the "
                "project backlog; unfiled: open subtasks with no batch."
            )
        ),
    ],
    project: ProjectAlias = None,
) -> BacklogOutput:
    """
    List a project's backlog items of one scope.

    Args:
        - ctx (Context): the request context.
        - scope (BacklogScope): session, project or unfiled.
        - project (str | None): an alias; resolved from roots or cwd if None.

    Returns:
        - output (BacklogOutput): up to BACKLOG_MAX items and a truncated flag.
    """
    roots = await root_paths(ctx, project)

    def work(store: Store) -> BacklogOutput:
        found, resolved_by = resolve_project(store, project, roots)
        with store.read() as conn:
            book = KeyBook(conn)
            items = [
                item
                for item in item_db.list_for_project(conn, found.id)
                if _in_scope(scope, item, book.category(item))
            ]
            return BacklogOutput(
                project=found.key_prefix,
                resolved_by=resolved_by,
                scope=scope,
                items=[item_summary(book, item) for item in items[:BACKLOG_MAX]],
                truncated=len(items) > BACKLOG_MAX,
            )

    return await run_db(ctx, work)


def _children(book: KeyBook, children: list[Item]) -> ChildrenSummary:
    by_category: dict[Category, int] = {}
    for child in children:
        category = book.category(child)
        if category is not None:
            by_category[category] = by_category.get(category, 0) + 1
    return ChildrenSummary(
        total=len(children),
        by_category=by_category,
        items=[item_summary(book, child) for child in children[:CHILDREN_MAX]],
        truncated=len(children) > CHILDREN_MAX,
    )


def _in_scope(scope: BacklogScope, item: Item, category: Category | None) -> bool:
    if scope == "unfiled":
        return item.unfiled and category not in TERMINAL_CATEGORIES
    if category is not Category.BACKLOGGED:
        return False
    return (item.backlog_session_id is not None) == (scope == "session")


def register(server: MCPServer) -> None:
    """
    Add the item read tools to a server.

    Args:
        - server (MCPServer): the server.
    """
    server.add_tool(
        tree_get,
        description=describe(
            "Item tree of a project in pre-order: goals > batches > subtasks, "
            "plus unfiled subtasks. Bounded by depth and limit; truncated says "
            f"whether items were hidden. {RESOLUTION}"
        ),
        annotations=READ,
    )
    server.add_tool(
        item_get,
        description=describe(
            "One item in full, a summary of its children and its 10 most recent "
            "events. Use its version as expected_version in item_update."
        ),
        annotations=READ,
    )
    server.add_tool(
        backlog_list,
        description=describe(
            "Backlog items of a project for one scope, by number, at most 100. "
            "Captured items appear in both the session scope and the unfiled "
            f"scope. {RESOLUTION}"
        ),
        annotations=READ,
    )
