"""Backlog write tools: capture, backlog_cover and backlog_push."""

from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from xoot.models.fields import Body, Title
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.subtree_plan import SubtreePlan
from xoot.models.project.project import Project
from xoot.repositories.item import item_db
from xoot.server.clients import write_context
from xoot.server.confirm import args_digest, confirmation
from xoot.server.db_call import run_db
from xoot.server.key_book import KeyBook
from xoot.server.render import (
    change_entry,
    completion,
    item_detail,
    item_summary,
    item_write_output,
)
from xoot.server.resolution import item_by_key, optional_item_id, resolve_project
from xoot.server.roots import root_paths
from xoot.server.schemas.affected_item_entry import AffectedItemEntry
from xoot.server.schemas.arguments import (
    ConfirmToken,
    ItemKey,
    OptionalItemKey,
    ProjectAlias,
)
from xoot.server.schemas.cover_output import CoverOutput
from xoot.server.schemas.item_write_output import ItemWriteOutput
from xoot.server.schemas.push_output import PushOutput
from xoot.server.schemas.subtree_output import SubtreeOutput
from xoot.server.tool_meta import DESTRUCTIVE, RESOLUTION, WRITE, describe
from xoot.services.backlog_push_service import apply_push, preview_push
from xoot.services.backlog_service import capture as capture_item
from xoot.services.backlog_service import cover
from xoot.services.confirm_service import issue_token
from xoot.store.store import Store

PUSH_TOOL = "backlog_push"


async def backlog_cover(
    ctx: Context,
    key: ItemKey,
    batch: Annotated[
        OptionalItemKey,
        Field(
            description=(
                "Batch to add the subtask to. Defaults to the item's own batch; "
                "required for an item on a goal (a batch of that goal) or on "
                "the project (a batch of any goal)."
            )
        ),
    ] = None,
    project: ProjectAlias = None,
) -> CoverOutput:
    """
    Turn a backlog item into a subtask and close it.

    Args:
        - ctx (Context): the request context.
        - key (str): the backlog item key.
        - batch (str | None): the batch to cover it in.
        - project (str | None): an alias; resolved from the keys, roots or cwd.

    Returns:
        - output (CoverOutput): the subtask, the closed item and the outcome.
    """
    roots = await root_paths(ctx, project)
    write = write_context(ctx)

    def work(store: Store) -> CoverOutput:
        found, _ = resolve_project(store, project, roots, [key, batch])
        with store.read() as conn:
            backlog_id = item_by_key(conn, found, key).id
            batch_id = optional_item_id(conn, found, batch)
        subtask, closed, report = cover(store, backlog_id, batch_id, write)
        with store.read() as conn:
            book = KeyBook(conn)
            return CoverOutput(
                project=found.key_prefix,
                subtask=item_detail(book, subtask),
                backlog=item_summary(book, closed),
                **completion(report),
            )

    return await run_db(ctx, work)


async def backlog_push(
    ctx: Context,
    key: ItemKey,
    project: ProjectAlias = None,
    confirm_token: ConfirmToken = None,
) -> PushOutput:
    """
    Move a backlog item one level up, previewed first.

    Args:
        - ctx (Context): the request context.
        - key (str): the backlog item key.
        - project (str | None): an alias; resolved from the key, roots or cwd.
        - confirm_token (str | None): the preview's token, to apply.

    Returns:
        - output (PushOutput): the plan and a token, or the applied move.
    """
    roots = await root_paths(ctx, project)
    write = write_context(ctx)
    digest = args_digest({"project": project, "key": key})

    def work(store: Store) -> PushOutput:
        found, _ = resolve_project(store, project, roots, [key])
        with store.read() as conn:
            item_id = item_by_key(conn, found, key).id
        if confirm_token is None:
            plan = preview_push(store, item_id)
            token = issue_token(store, found.id, PUSH_TOOL, digest, plan.plan_sha256)
            return _output(store, found, plan, token)
        claim = confirmation(PUSH_TOOL, confirm_token, digest)
        plan, report = apply_push(store, item_id, write, claim)
        return _output(store, found, plan, None).model_copy(update=completion(report))

    return await run_db(ctx, work)


# One parameter per tool argument: the SDK derives the input schema from it.
async def capture(  # pylint: disable=too-many-arguments
    ctx: Context,
    *,
    found_on: Annotated[
        ItemKey,
        Field(description="Key of the item the work was found on (any kind)."),
    ],
    title: Title,
    body: Annotated[Body, Field(description="Why this needs doing.")],
    project: ProjectAlias = None,
) -> ItemWriteOutput:
    """
    Capture open work found along the way as a backlog item.

    Args:
        - ctx (Context): the request context.
        - found_on (str): the item it was found on.
        - title (str): the item title.
        - body (str): the why.
        - project (str | None): an alias; resolved from the key, roots or cwd.

    Returns:
        - output (ItemWriteOutput): the backlog item and the completion outcome.
    """
    roots = await root_paths(ctx, project)
    write = write_context(ctx)

    def work(store: Store) -> ItemWriteOutput:
        found, _ = resolve_project(store, project, roots, [found_on])
        with store.read() as conn:
            found_on_id = item_by_key(conn, found, found_on).id
        draft = ItemDraft(title=title, body=body)
        item, report = capture_item(store, found.id, found_on_id, draft, write)
        with store.read() as conn:
            return item_write_output(conn, found, item, report)

    return await run_db(ctx, work)


def _output(
    store: Store, project: Project, plan: SubtreePlan, token: str | None
) -> PushOutput:
    """Render a push plan; an applied one also carries the item as it now stands."""
    with store.read() as conn:
        book = KeyBook(conn)
        root = item_db.get(conn, plan.root_id)
        row = None if token is not None else root
        return PushOutput(
            project=project.key_prefix,
            phase="preview" if token is not None else "applied",
            confirm_token=token,
            plan=SubtreeOutput(
                root="" if root is None else root.key,
                changes=[change_entry(book, change) for change in plan.changes],
            ),
            item=(
                None
                if row is None
                else AffectedItemEntry(
                    key=row.key,
                    state=row.state,
                    parent=book.item_key(row.parent_id),
                    version=row.version,
                )
            ),
        )


def register(server: MCPServer) -> None:
    """
    Add the backlog write tools to a server.

    Args:
        - server (MCPServer): the server.
    """
    server.add_tool(
        capture,
        description=describe(
            "Capture open work found along the way the moment it appears. "
            "found_on is the item it was found on; the body says why. It lands "
            "on the batch of a subtask or batch, on a goal, or on the project "
            "beside a project-level backlog item, and reopens a done batch or "
            "goal. Check backlog_list first; never capture a duplicate. "
            f"{RESOLUTION}"
        ),
        annotations=WRITE,
    )
    server.add_tool(
        backlog_cover,
        description=describe(
            "Turn an open backlog item into a subtask (same title and body) and "
            "close the item. The subtask goes in the item's batch, or in the "
            "named batch: required for an item on a goal (a batch of that "
            "goal) or on the project (a batch of any goal). To resolve an "
            "item without a subtask, set it to its done state with "
            f"item_update instead. {RESOLUTION}"
        ),
        annotations=WRITE,
    )
    server.add_tool(
        backlog_push,
        description=describe(
            "Move an open backlog item one level up: batch to goal, goal to "
            "project. It takes a new key there; the old key keeps resolving. "
            "First call returns the plan and a confirm_token and writes "
            "nothing else; call again with the same arguments plus the token. "
            f"{RESOLUTION}"
        ),
        annotations=DESTRUCTIVE,
    )
