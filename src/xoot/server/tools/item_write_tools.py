"""Item create tools: capture, item_create and items_create_bulk."""

import sqlite3
from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from xoot.models.fields import Body, Title
from xoot.models.item.bulk_create import MAX_BULK_ITEMS, BulkCreate
from xoot.models.item.bulk_item import BulkItem
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.server.confirm import args_digest, confirmation
from xoot.server.db_call import run_db
from xoot.server.key_book import KeyBook
from xoot.server.render import item_detail, item_summary
from xoot.server.resolution import optional_item_id, session_writer
from xoot.server.schemas.arguments import ConfirmToken, SessionKey
from xoot.server.schemas.bulk_item_input import BulkItemInput
from xoot.server.schemas.bulk_output import BulkOutput
from xoot.server.schemas.item_detail import ItemDetail
from xoot.server.schemas.planned_entry import PlannedEntry
from xoot.server.tool_meta import WRITE, describe
from xoot.services.bulk_service import apply_bulk, preview_bulk
from xoot.services.confirm_service import issue_token
from xoot.services.item_service import capture as capture_item
from xoot.services.item_service import create_item
from xoot.store.store import Store

BULK_TOOL = "items_create_bulk"


async def capture(
    ctx: Context, session: SessionKey, title: Title, body: Body = ""
) -> ItemDetail:
    """
    Capture a side item into the session's backlog.

    Args:
        - ctx (Context): the request context.
        - session (str): the open session key.
        - title (str): the item title.
        - body (str): optional details.

    Returns:
        - item (ItemDetail): the new unfiled subtask.
    """

    def work(store: Store) -> ItemDetail:
        found, write = session_writer(store, session)
        draft = ItemDraft(title=title, body=body)
        item = capture_item(store, found.id, draft, write.actor)
        with store.read() as conn:
            return item_detail(KeyBook(conn), item)

    return await run_db(ctx, work)


# One parameter per tool argument: the SDK derives the input schema from it.
async def item_create(  # pylint: disable=too-many-arguments
    ctx: Context,
    *,
    session: SessionKey,
    kind: ItemKind,
    title: Title,
    body: Body = "",
    parent: Annotated[
        str | None,
        Field(
            description="Parent item key: a goal for a batch, a batch for a subtask."
        ),
    ] = None,
) -> ItemDetail:
    """
    Create one goal, batch or subtask in the session's project.

    Args:
        - ctx (Context): the request context.
        - session (str): the open session key.
        - kind (ItemKind): goal, batch or subtask.
        - title (str): the item title.
        - body (str): optional details.
        - parent (str | None): the parent item key.

    Returns:
        - item (ItemDetail): the new item.
    """

    def work(store: Store) -> ItemDetail:
        found, write = session_writer(store, session)
        with store.read() as conn:
            parent_id = optional_item_id(conn, parent)
        request = ItemCreate(kind=kind, title=title, body=body, parent_id=parent_id)
        item = create_item(store, found.project_id, request, write)
        with store.read() as conn:
            return item_detail(KeyBook(conn), item)

    return await run_db(ctx, work)


async def items_create_bulk(
    ctx: Context,
    session: SessionKey,
    items: Annotated[
        list[BulkItemInput],
        Field(min_length=1, max_length=MAX_BULK_ITEMS),
    ],
    confirm_token: ConfirmToken = None,
) -> BulkOutput:
    """
    Create a tree of items in one transaction, previewed first.

    Args:
        - ctx (Context): the request context.
        - session (str): the open session key.
        - items (list[BulkItemInput]): top-level nodes with nested children.
        - confirm_token (str | None): the preview's token, to apply.

    Returns:
        - output (BulkOutput): the plan and a token, or the created items.
    """
    digest = args_digest(
        {"session": session, "items": [node.model_dump(mode="json") for node in items]}
    )

    def work(store: Store) -> BulkOutput:
        found, write = session_writer(store, session)
        with store.read() as conn:
            request = BulkCreate(items=tuple(_bulk_item(conn, node) for node in items))
        if confirm_token is None:
            plan = preview_bulk(store, found.id, request)
            token = issue_token(store, found.id, BULK_TOOL, digest, plan.plan_sha256)
            planned = [
                PlannedEntry(key=p.key, kind=p.kind, title=p.title, parent=p.parent_key)
                for p in plan.items
            ]
            return BulkOutput(
                phase="preview", confirm_token=token, planned=planned, created=[]
            )
        claim = confirmation(BULK_TOOL, confirm_token, digest)
        created = apply_bulk(store, found.id, request, write.actor, claim)
        with store.read() as conn:
            book = KeyBook(conn)
            summaries = [item_summary(book, item) for item in created]
        return BulkOutput(
            phase="applied", confirm_token=None, planned=[], created=summaries
        )

    return await run_db(ctx, work)


def _bulk_item(conn: sqlite3.Connection, node: BulkItemInput) -> BulkItem:
    """Translate a node's parent key to an id, recursively."""
    return BulkItem(
        kind=node.kind,
        title=node.title,
        body=node.body,
        parent_id=optional_item_id(conn, node.parent),
        children=tuple(_bulk_item(conn, child) for child in node.children),
    )


def register(server: MCPServer) -> None:
    """
    Add the item create tools to a server.

    Args:
        - server (MCPServer): the server.
    """
    server.add_tool(
        capture,
        description=describe(
            "Capture a side item the moment it appears: an unfiled subtask "
            "parked in this session's backlog. Cheap; do not wait."
        ),
        annotations=WRITE,
    )
    server.add_tool(
        item_create,
        description=describe(
            "Create one goal, batch or subtask in the session's project. A "
            "batch needs a parent goal; a subtask takes a parent batch or none."
        ),
        annotations=WRITE,
    )
    server.add_tool(
        items_create_bulk,
        description=describe(
            "Create a nested tree of up to 50 items in one transaction. First "
            "call returns the planned keys and a confirm_token and writes "
            "nothing else; call again with the same arguments plus the token."
        ),
        annotations=WRITE,
    )
