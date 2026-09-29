"""
The item_update tool and its three paths.

A parent change goes through the subtree reparent, and a drop of an item with
children through the subtree drop. On an item with children both are
two-phase, since they move or change the whole subtree. Anything else is a
direct update, including resolving a backlog item by moving it to its done
state. A parent change or a subtree drop must come alone: combining it with
other fields would need two transactions. Those rules live in
services.update_paths, which paste mode shares.

The path is chosen from a read snapshot, so a path that skips the preview
re-checks under the write lock that the item still has no children to drop
or carry; if it has, nothing is written and the caller must preview.
"""

import sqlite3

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from xoot.exceptions.update_path_error import UpdatePathError
from xoot.models.event.write_context import WriteContext
from xoot.models.item.completion_report import CompletionReport
from xoot.models.item.item import Item
from xoot.models.item.item_changes_input import ItemChangesInput
from xoot.models.item.item_update import ItemUpdate
from xoot.models.item.subtree_plan import SubtreePlan
from xoot.models.project.project import Project
from xoot.server.clients import write_context
from xoot.server.confirm import args_digest, confirmation
from xoot.server.db_call import run_db
from xoot.server.key_book import KeyBook
from xoot.server.render import completion, item_detail
from xoot.server.resolution import (
    decision_by_key,
    item_by_key,
    optional_item_id,
    resolve_project,
)
from xoot.server.roots import root_paths
from xoot.server.schemas.arguments import (
    ConfirmToken,
    ExpectedVersion,
    ItemKey,
    ProjectAlias,
)
from xoot.server.schemas.item_update_output import ItemUpdateOutput
from xoot.server.subtree_change import SubtreeChange, plan_output
from xoot.server.tool_meta import DESTRUCTIVE, RESOLUTION, describe
from xoot.services import update_paths
from xoot.services.confirm_service import issue_token
from xoot.services.item_service import update_item_in
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store

TOOL = "item_update"
PREVIEW_REQUIRED = "preview required: the item now has children"


# One parameter per tool argument: the SDK derives the input schema from it.
async def item_update(  # pylint: disable=too-many-arguments
    ctx: Context,
    *,
    key: ItemKey,
    expected_version: ExpectedVersion,
    changes: ItemChangesInput,
    project: ProjectAlias = None,
    confirm_token: ConfirmToken = None,
) -> ItemUpdateOutput:
    """
    Change an item, previewing subtree drops and moves first.

    Args:
        - ctx (Context): the request context.
        - key (str): the item key.
        - expected_version (int): the version the caller read.
        - changes (ItemChangesInput): the fields to change.
        - project (str | None): an alias; resolved from keys, roots or cwd.
        - confirm_token (str | None): the preview's token, to apply; ignored
          on paths that need no confirmation.

    Returns:
        - output (ItemUpdateOutput): the updated item, or a plan.
    """
    roots = await root_paths(ctx, project)
    write = write_context(ctx)
    digest = args_digest(
        {
            "project": project,
            "key": key,
            "expected_version": expected_version,
            "changes": changes.model_dump(mode="json", exclude_unset=True),
        }
    )
    keys = [key, changes.parent, changes.awaiting_decision]

    def work(store: Store) -> ItemUpdateOutput:
        found, _ = resolve_project(store, project, roots, keys)
        with store.read() as conn:
            item = item_by_key(conn, found, key)
            request, has_children = _request(
                conn, found, item, changes, expected_version, write
            )
        if isinstance(request, ItemUpdate):
            updated, report = _direct_update(
                store, item, expected_version, request, write
            )
            with store.read() as conn:
                detail = item_detail(KeyBook(conn), updated)
            return ItemUpdateOutput(
                project=found.key_prefix,
                mode="update",
                phase="applied",
                confirm_token=None,
                item=detail,
                plan=None,
                **completion(report),
            )
        if not has_children:
            plan, report = _direct_subtree(store, item, request)
            return plan_output(store, request, "applied", None, plan, report)
        if confirm_token is None:
            plan = request.preview(store)
            token = issue_token(store, found.id, TOOL, digest, plan.plan_sha256)
            return plan_output(store, request, "preview", token, plan)
        claim = confirmation(TOOL, confirm_token, digest)
        plan, report = request.apply(store, claim)
        return plan_output(store, request, "applied", None, plan, report)

    return await run_db(ctx, work)


def _direct_update(
    store: Store,
    item: Item,
    expected_version: int,
    request: ItemUpdate,
    write: WriteContext,
) -> tuple[Item, CompletionReport]:
    """Apply an update chosen without a preview, unless it now drops a parent."""
    with store.write() as conn:
        state = request.provided().get("state")
        if update_paths.drops(conn, item, state) and update_paths.has_children(
            conn, item
        ):
            raise ToolError(PREVIEW_REQUIRED)
        scope = WriteScope(conn, write)
        updated = update_item_in(scope, item.id, expected_version, request)
        return updated, scope.report()


def _direct_subtree(
    store: Store, item: Item, request: SubtreeChange
) -> tuple[SubtreePlan, CompletionReport]:
    """Apply a subtree change chosen as childless, unless it now has children."""
    with store.write() as conn:
        if update_paths.has_children(conn, item):
            raise ToolError(PREVIEW_REQUIRED)
        scope = WriteScope(conn, request.write)
        return request.apply_in(scope), scope.report()


# Six arguments: the call's project, item, changes, version and actor.
def _request(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    conn: sqlite3.Connection,
    project: Project,
    item: Item,
    changes: ItemChangesInput,
    expected_version: int,
    write: WriteContext,
) -> tuple[ItemUpdate | SubtreeChange, bool]:
    """Pick the path and resolve its keys; the bool says whether the item has children."""
    try:
        mode, children = update_paths.choose_path(
            conn, item, changes.model_fields_set, changes.state
        )
    except UpdatePathError as exc:
        raise ToolError(str(exc)) from exc
    if mode == "update":
        update = update_paths.item_update_from(
            changes, lambda key: decision_by_key(conn, project, key).id
        )
        return update, children
    subtree = SubtreeChange(
        mode=mode,
        project=project.key_prefix,
        item_id=item.id,
        key=item.key,
        new_parent_id=optional_item_id(conn, project, changes.parent),
        state=changes.state if mode == "drop" else None,
        expected_version=expected_version,
        write=write,
    )
    return subtree, children


def register(server: MCPServer) -> None:
    """
    Add item_update to a server.

    Args:
        - server (MCPServer): the server.
    """
    server.add_tool(
        item_update,
        description=describe(
            "Change an item's title, body, state, parent or awaited decision, "
            "passing expected_version from your last read. Take state names "
            "from the workflow in brief_get. Resolve a backlog item directly "
            "by setting its done state. Goals and batches complete and reopen "
            "on their own; the result lists what completed, reopened or stays "
            "blocked by open backlog. A parent change re-keys the item and its "
            "subtree (old keys keep resolving). Send a parent change, or a "
            "drop of an item with children, alone; on an item with children "
            "those two first return a plan and a confirm_token and write "
            "nothing else; call again with the same arguments plus the token. "
            f"{RESOLUTION}"
        ),
        annotations=DESTRUCTIVE,
    )
