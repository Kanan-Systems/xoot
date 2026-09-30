"""Item create tools: item_create and items_create_bulk."""

import sqlite3
from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from xoot.models.fields import Body, Title
from xoot.models.item.bulk_create import MAX_BULK_ITEMS, BulkCreate
from xoot.models.item.bulk_item import BulkItem
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.server.clients import write_context
from xoot.server.confirm import args_digest, confirmation
from xoot.server.db_call import run_db
from xoot.server.key_book import KeyBook
from xoot.server.render import completion, item_summary, item_write_output
from xoot.server.resolution import optional_item_id, resolve_project
from xoot.server.roots import root_paths
from xoot.server.schemas.arguments import ConfirmToken, OptionalItemKey, ProjectAlias
from xoot.server.schemas.bulk_item_input import BulkItemInput
from xoot.server.schemas.bulk_output import BulkOutput
from xoot.server.schemas.item_write_output import ItemWriteOutput
from xoot.server.schemas.literals import WorkKind
from xoot.server.schemas.planned_entry import PlannedEntry
from xoot.server.tool_meta import RESOLUTION, WRITE, describe
from xoot.services.bulk_service import apply_bulk, preview_bulk
from xoot.services.confirm_service import issue_token
from xoot.services.item_service import create_item
from xoot.store.store import Store

BULK_TOOL = "items_create_bulk"


# One parameter per tool argument: the SDK derives the input schema from it.
async def item_create(  # pylint: disable=too-many-arguments
    ctx: Context,
    *,
    kind: WorkKind,
    title: Title,
    body: Body = "",
    parent: Annotated[
        OptionalItemKey,
        Field(description="Parent key: a goal for a batch, a batch for a subtask."),
    ] = None,
    project: ProjectAlias = None,
) -> ItemWriteOutput:
    """
    Create one goal, batch or subtask.

    Args:
        - ctx (Context): the request context.
        - kind (str): goal, batch or subtask.
        - title (str): the item title.
        - body (str): optional details.
        - parent (str | None): the parent item key.
        - project (str | None): an alias; resolved from keys, roots or cwd.

    Returns:
        - output (ItemWriteOutput): the new item and the completion outcome.
    """
    roots = await root_paths(ctx, project)
    write = write_context(ctx)

    def work(store: Store) -> ItemWriteOutput:
        found, _ = resolve_project(store, project, roots, [parent])
        with store.read() as conn:
            parent_id = optional_item_id(conn, found, parent)
        request = ItemCreate(
            kind=ItemKind(kind), title=title, body=body, parent_id=parent_id
        )
        item, report = create_item(store, found.id, request, write)
        with store.read() as conn:
            return item_write_output(conn, found, item, report)

    return await run_db(ctx, work)


async def items_create_bulk(
    ctx: Context,
    items: Annotated[
        list[BulkItemInput],
        Field(min_length=1, max_length=MAX_BULK_ITEMS),
    ],
    project: ProjectAlias = None,
    confirm_token: ConfirmToken = None,
) -> BulkOutput:
    """
    Create a tree of items in one transaction, previewed first.

    Args:
        - ctx (Context): the request context.
        - items (list[BulkItemInput]): top-level nodes with nested children.
        - project (str | None): an alias; resolved from keys, roots or cwd.
        - confirm_token (str | None): the preview's token, to apply.

    Returns:
        - output (BulkOutput): the plan and a token, or the created items.
    """
    roots = await root_paths(ctx, project)
    write = write_context(ctx)
    digest = args_digest(
        {"project": project, "items": [node.model_dump(mode="json") for node in items]}
    )
    parents = [node.parent for node in items]

    def work(store: Store) -> BulkOutput:
        found, _ = resolve_project(store, project, roots, parents)
        with store.read() as conn:
            request = BulkCreate(
                items=tuple(_bulk_item(conn, found, node) for node in items)
            )
        if confirm_token is None:
            plan = preview_bulk(store, found.id, request)
            token = issue_token(
                store, found.id, BULK_TOOL, digest, plan.plan_sha256, actor=write.actor
            )
            planned = [
                PlannedEntry(key=p.key, kind=p.kind, title=p.title, parent=p.parent_key)
                for p in plan.items
            ]
            return BulkOutput(
                project=found.key_prefix,
                phase="preview",
                confirm_token=token,
                planned=planned,
                created=[],
            )
        claim = confirmation(BULK_TOOL, confirm_token, digest)
        created, report = apply_bulk(store, found.id, request, write, claim)
        with store.read() as conn:
            book = KeyBook(conn)
            summaries = [item_summary(book, item) for item in created]
        return BulkOutput(
            project=found.key_prefix,
            phase="applied",
            confirm_token=None,
            planned=[],
            created=summaries,
            **completion(report),
        )

    return await run_db(ctx, work)


def _bulk_item(
    conn: sqlite3.Connection, project: Project, node: BulkItemInput
) -> BulkItem:
    """Translate a node's parent key to an id, recursively."""
    return BulkItem(
        kind=ItemKind(node.kind),
        title=node.title,
        body=node.body,
        parent_id=optional_item_id(conn, project, node.parent),
        children=tuple(_bulk_item(conn, project, child) for child in node.children),
    )


def register(server: MCPServer) -> None:
    """
    Add the item create tools to a server.

    Args:
        - server (MCPServer): the server.
    """
    server.add_tool(
        item_create,
        description=describe(
            "Create one goal, batch or subtask. A goal sits on the project, a "
            "batch needs a parent goal, a subtask a parent batch; each gets "
            "the next number of its parent, e.g. goal-1/batch-2/subtask-3. A "
            "new subtask reopens a done batch and goal. The result lists what "
            f"completed, reopened or stays blocked. {RESOLUTION}"
        ),
        annotations=WRITE,
    )
    server.add_tool(
        items_create_bulk,
        description=describe(
            "Create a nested tree of up to 50 goals, batches and subtasks in "
            "one transaction. First call returns the planned keys and a "
            "confirm_token and writes nothing else; call again with the same "
            f"arguments plus the token. {RESOLUTION}"
        ),
        annotations=WRITE,
    )
