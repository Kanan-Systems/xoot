"""Item read tools: tree_get, item_get and backlog_list."""

from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from xoot.models.item.tree_query import MAX_DEPTH, MAX_ITEMS, TreeQuery
from xoot.repositories.item import item_db
from xoot.server.db_call import run_db
from xoot.server.key_book import KeyBook
from xoot.server.render import (
    children_summary,
    decision_summary,
    event_entry,
    item_detail,
    item_summary,
    tree_entries,
)
from xoot.server.resolution import item_by_key, optional_item_id, resolve_project
from xoot.server.roots import root_paths
from xoot.server.schemas.arguments import ItemKey, OptionalItemKey, ProjectAlias
from xoot.server.schemas.backlog_entry import BacklogEntry
from xoot.server.schemas.backlog_output import BacklogOutput
from xoot.server.schemas.item_get_output import ItemGetOutput
from xoot.server.schemas.tree_output import TreeOutput
from xoot.server.tool_meta import READ, RESOLUTION, describe
from xoot.services.backlog_reads import backlog_items, backlog_level
from xoot.services.decision_reads import owned_decisions
from xoot.services.history_service import recent_events
from xoot.services.tree_service import tree_in
from xoot.store.store import Store

RECENT_EVENTS = 10
CHILDREN_MAX = 25
DECISIONS_MAX = 25
BACKLOG_MAX = 100


# One parameter per tool argument: the SDK derives the input schema from it.
async def tree_get(  # pylint: disable=too-many-arguments
    ctx: Context,
    project: ProjectAlias = None,
    *,
    root: Annotated[
        OptionalItemKey,
        Field(description="Item key to start from; the goals when omitted."),
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
        - project (str | None): an alias; resolved from keys, roots or cwd.
        - root (str | None): the item key to start from.
        - depth (int): levels below the roots.
        - include_done (bool): include done and dropped items.
        - limit (int): the most items to return.

    Returns:
        - output (TreeOutput): nodes in pre-order and a truncated flag.
    """
    roots = await root_paths(ctx, project)

    def work(store: Store) -> TreeOutput:
        found, resolved_by = resolve_project(store, project, roots, [root])
        with store.read() as conn:
            query = TreeQuery(
                root_id=optional_item_id(conn, found, root),
                depth=depth,
                max_items=limit,
                include_terminal=include_done,
            )
            result = tree_in(conn, found.id, query)
            return TreeOutput(
                project=found.key_prefix,
                resolved_by=resolved_by,
                nodes=tree_entries(KeyBook(conn), result),
                truncated=result.truncated,
            )

    return await run_db(ctx, work)


async def item_get(
    ctx: Context, key: ItemKey, project: ProjectAlias = None
) -> ItemGetOutput:
    """
    Return one item with its children, decisions and recent events.

    Args:
        - ctx (Context): the request context.
        - key (str): the item key; an old key of a moved item works too.
        - project (str | None): an alias; resolved from the key, roots or cwd.

    Returns:
        - output (ItemGetOutput): the item, children, decisions and events.
    """
    roots = await root_paths(ctx, project)

    def work(store: Store) -> ItemGetOutput:
        found, _ = resolve_project(store, project, roots, [key])
        with store.read() as conn:
            book = KeyBook(conn)
            item = item_by_key(conn, found, key)
            children = item_db.list_children(conn, item.project_id, [item.id])
            decisions = owned_decisions(conn, item, DECISIONS_MAX)
            events = recent_events(conn, item.id, RECENT_EVENTS)
            return ItemGetOutput(
                project=found.key_prefix,
                item=item_detail(book, item),
                children=children_summary(book, children, CHILDREN_MAX),
                decisions=[decision_summary(book, d) for d in decisions],
                events=[event_entry(book, e) for e in events],
            )

    return await run_db(ctx, work)


async def backlog_list(
    ctx: Context,
    project: ProjectAlias = None,
    at: Annotated[
        OptionalItemKey,
        Field(
            description=(
                "A goal or batch key: only the backlog sitting on it. Omit for "
                "the whole project, every level."
            )
        ),
    ] = None,
    include_closed: Annotated[
        bool, Field(description="Also list done and dropped backlog items.")
    ] = False,
) -> BacklogOutput:
    """
    List backlog items: a whole project's, or those on one goal or batch.

    Args:
        - ctx (Context): the request context.
        - project (str | None): an alias; resolved from keys, roots or cwd.
        - at (str | None): a goal or batch key.
        - include_closed (bool): include done and dropped items.

    Returns:
        - output (BacklogOutput): up to BACKLOG_MAX items and a truncated flag.
    """
    roots = await root_paths(ctx, project)

    def work(store: Store) -> BacklogOutput:
        found, resolved_by = resolve_project(store, project, roots, [at])
        with store.read() as conn:
            book = KeyBook(conn)
            target = None if at is None else item_by_key(conn, found, at)
            items = backlog_items(conn, found.id, target, include_closed)
            return BacklogOutput(
                project=found.key_prefix,
                resolved_by=resolved_by,
                at=None if target is None else target.key,
                items=[
                    BacklogEntry(
                        **item_summary(book, item).model_dump(),
                        level=backlog_level(item),
                        found_on=book.item_key(item.found_on_item_id),
                    )
                    for item in items[:BACKLOG_MAX]
                ],
                truncated=len(items) > BACKLOG_MAX,
            )

    return await run_db(ctx, work)


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
            "each level's backlog after its work, and the project backlog. "
            "Bounded by depth and limit; truncated says whether items were "
            f"hidden. {RESOLUTION}"
        ),
        annotations=READ,
    )
    server.add_tool(
        item_get,
        description=describe(
            "One item in full (body, backlog links, old keys), a summary of its "
            "children, the decisions made on it and its 10 most recent events. "
            "An old key of a moved item still resolves. Use its version as "
            f"expected_version in item_update. {RESOLUTION}"
        ),
        annotations=READ,
    )
    server.add_tool(
        backlog_list,
        description=describe(
            "Open backlog items of a project, or of one goal or batch (at), "
            "project level first, at most 100, with the level each sits on and "
            "the item it was found on. Check it before capture so you never "
            f"create a duplicate. {RESOLUTION}"
        ),
        annotations=READ,
    )
