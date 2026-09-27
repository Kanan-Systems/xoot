"""
The item_update tool and its three paths.

A parent change goes through the subtree reparent, and a drop of an item with
children through the subtree drop. On an item with children both are
two-phase, since they move or change the whole subtree. Anything else is a
direct update. A parent change or a subtree drop must come alone: combining
it with other fields would need two transactions.

The path is chosen from a read snapshot, so a path that skips the preview
re-checks under the write lock that the item still has no children to drop
or carry; if it has, nothing is written and the caller must preview.
"""

import sqlite3
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ConfigDict

from xoot.models.confirm.confirmation import Confirmation
from xoot.models.event.write_context import WriteContext
from xoot.models.fields import Id, StateName
from xoot.models.item.item import Item
from xoot.models.item.item_update import ItemUpdate
from xoot.models.item.subtree_plan import SubtreePlan
from xoot.models.workflow.category import Category
from xoot.repositories.item import item_db
from xoot.server.confirm import args_digest, confirmation
from xoot.server.db_call import run_db
from xoot.server.key_book import KeyBook
from xoot.server.render import change_entry, item_detail
from xoot.server.resolution import (
    decision_by_key,
    item_by_key,
    optional_item_id,
    session_by_key,
    session_writer,
)
from xoot.server.schemas.affected_item_entry import AffectedItemEntry
from xoot.server.schemas.arguments import (
    ConfirmToken,
    ExpectedVersion,
    ItemKey,
    SessionKey,
)
from xoot.server.schemas.item_changes_input import ItemChangesInput
from xoot.server.schemas.item_update_output import ItemUpdateOutput
from xoot.server.schemas.literals import Phase, UpdateMode
from xoot.server.schemas.subtree_output import SubtreeOutput
from xoot.server.tool_meta import DESTRUCTIVE, describe
from xoot.services.confirm_service import issue_token
from xoot.services.item_service import update_item_in
from xoot.services.subtree_service import (
    apply_drop_in,
    apply_reparent_in,
    preview_drop,
    preview_reparent,
)
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store

TOOL = "item_update"
ALONE = (
    "{} must be the only field in changes; send the other changes in a "
    "separate item_update call"
)
PREVIEW_REQUIRED = "preview required: the item now has children"


# One parameter per tool argument: the SDK derives the input schema from it.
async def item_update(  # pylint: disable=too-many-arguments
    ctx: Context,
    *,
    session: SessionKey,
    key: ItemKey,
    expected_version: ExpectedVersion,
    changes: ItemChangesInput,
    confirm_token: ConfirmToken = None,
) -> ItemUpdateOutput:
    """
    Change an item, previewing subtree drops and moves first.

    Args:
        - ctx (Context): the request context.
        - session (str): the open session key.
        - key (str): the item key.
        - expected_version (int): the version the caller read.
        - changes (ItemChangesInput): the fields to change.
        - confirm_token (str | None): the preview's token, to apply; ignored
          on paths that need no confirmation.

    Returns:
        - output (ItemUpdateOutput): the updated item, or a plan.
    """
    digest = args_digest(
        {
            "session": session,
            "key": key,
            "expected_version": expected_version,
            "changes": changes.model_dump(mode="json", exclude_unset=True),
        }
    )

    def work(store: Store) -> ItemUpdateOutput:
        found, write = session_writer(store, session)
        with store.read() as conn:
            item = item_by_key(conn, key)
            request, has_children = _request(
                conn, item, changes, expected_version, write
            )
        if isinstance(request, ItemUpdate):
            updated = _direct_update(store, item, expected_version, request, write)
            with store.read() as conn:
                detail = item_detail(KeyBook(conn), updated)
            return ItemUpdateOutput(
                mode="update",
                phase="applied",
                confirm_token=None,
                item=detail,
                plan=None,
            )
        if not has_children:
            plan = _direct_subtree(store, item, request)
            return _plan_output(store, request, "applied", None, plan)
        if confirm_token is None:
            plan = request.preview(store)
            token = issue_token(store, found.id, TOOL, digest, plan.plan_sha256)
            return _plan_output(store, request, "preview", token, plan)
        claim = confirmation(TOOL, confirm_token, digest)
        return _plan_output(
            store, request, "applied", None, request.apply(store, claim)
        )

    return await run_db(ctx, work)


class _SubtreeChange(BaseModel):
    """One item's subtree drop or reparent, resolved and ready to preview or apply."""

    model_config = ConfigDict(frozen=True)

    mode: UpdateMode
    item_id: Id
    key: str
    new_parent_id: Id | None
    # The dropped state asked for; drop only.
    state: StateName | None
    expected_version: Id
    write: WriteContext

    def preview(self, store: Store) -> SubtreePlan:
        """
        Plan the change without writing.

        Args:
            - store (Store): the database.

        Returns:
            - plan (SubtreePlan): the planned changes.
        """
        if self.mode == "drop":
            return preview_drop(store, self.item_id, self.state)
        return preview_reparent(store, self.item_id, self.new_parent_id)

    def apply(self, store: Store, claim: Confirmation | None = None) -> SubtreePlan:
        """
        Write the change in its own transaction, consuming the token when one
        is given.

        Args:
            - store (Store): the database.
            - claim (Confirmation | None): the preview's token claim.

        Returns:
            - plan (SubtreePlan): the changes written.
        """
        with store.write() as conn:
            return self.apply_in(WriteScope(conn, self.write), claim)

    def apply_in(
        self, scope: WriteScope, claim: Confirmation | None = None
    ) -> SubtreePlan:
        """
        Write the change; the caller owns the transaction.

        Args:
            - scope (WriteScope): the open write scope.
            - claim (Confirmation | None): the preview's token claim.

        Returns:
            - plan (SubtreePlan): the changes written.
        """
        if self.mode == "drop":
            return apply_drop_in(
                scope, self.item_id, self.expected_version, claim, state=self.state
            )
        return apply_reparent_in(
            scope,
            self.item_id,
            self.new_parent_id,
            self.expected_version,
            confirm=claim,
        )


def _has_children(conn: sqlite3.Connection, item: Item) -> bool:
    return bool(item_db.list_children(conn, item.project_id, [item.id]))


def _drops(conn: sqlite3.Connection, item: Item, state: str | None) -> bool:
    """Whether moving the item to state puts it in the dropped category."""
    return state is not None and KeyBook(conn).category(item, state) is Category.DROPPED


def _direct_update(
    store: Store,
    item: Item,
    expected_version: int,
    request: ItemUpdate,
    write: WriteContext,
) -> Item:
    """Apply an update chosen without a preview, unless it now drops a parent."""
    with store.write() as conn:
        state = request.provided().get("state")
        if _drops(conn, item, state) and _has_children(conn, item):
            raise ToolError(PREVIEW_REQUIRED)
        scope = WriteScope(conn, write)
        return update_item_in(scope, item.id, expected_version, request)


def _direct_subtree(store: Store, item: Item, request: _SubtreeChange) -> SubtreePlan:
    """Apply a subtree change chosen as childless, unless it now has children."""
    with store.write() as conn:
        if _has_children(conn, item):
            raise ToolError(PREVIEW_REQUIRED)
        return request.apply_in(WriteScope(conn, request.write))


def _request(
    conn: sqlite3.Connection,
    item: Item,
    changes: ItemChangesInput,
    expected_version: int,
    write: WriteContext,
) -> tuple[ItemUpdate | _SubtreeChange, bool]:
    """Pick the path and resolve its keys; the bool says whether the item has children."""
    provided = changes.model_fields_set
    has_children = _has_children(conn, item)
    mode: UpdateMode = "update"
    if "parent" in provided:
        if provided != {"parent"}:
            raise ToolError(ALONE.format("parent"))
        mode = "reparent"
    elif has_children and _drops(conn, item, changes.state):
        if provided != {"state"}:
            raise ToolError(ALONE.format("a drop of an item with children"))
        mode = "drop"
    if mode == "update":
        return _item_update(conn, changes), has_children
    subtree = _SubtreeChange(
        mode=mode,
        item_id=item.id,
        key=item.key,
        new_parent_id=optional_item_id(conn, changes.parent),
        state=changes.state if mode == "drop" else None,
        expected_version=expected_version,
        write=write,
    )
    return subtree, has_children


def _item_update(conn: sqlite3.Connection, changes: ItemChangesInput) -> ItemUpdate:
    """Translate the key-based changes into the service's id-based update."""
    fields: dict[str, Any] = {}
    for name in changes.model_fields_set:
        value = getattr(changes, name)
        if name == "backlog_session":
            fields["backlog_session_id"] = (
                None if value is None else session_by_key(conn, value).id
            )
        elif name == "awaiting_decision":
            fields["awaiting_decision_id"] = (
                None if value is None else decision_by_key(conn, value).id
            )
        else:
            fields[name] = value
    return ItemUpdate(**fields)


def _plan_output(
    store: Store,
    request: _SubtreeChange,
    phase: Phase,
    token: str | None,
    plan: SubtreePlan,
) -> ItemUpdateOutput:
    with store.read() as conn:
        book = KeyBook(conn)
        keys = (book.item_key(item_id) for item_id in plan.carried_item_ids)
        output = SubtreeOutput(
            root=request.key,
            changes=[change_entry(book, change) for change in plan.changes],
            carried=[key for key in keys if key is not None],
        )
        items = None if phase == "preview" else _affected(conn, book, plan)
    return ItemUpdateOutput(
        mode=request.mode,
        phase=phase,
        confirm_token=token,
        item=None,
        items=items,
        plan=output,
    )


def _affected(
    conn: sqlite3.Connection, book: KeyBook, plan: SubtreePlan
) -> list[AffectedItemEntry]:
    """Every changed or carried item, read back after the write."""
    item_ids = [change.item_id for change in plan.changes]
    item_ids.extend(plan.carried_item_ids)
    rows = (item_db.get(conn, item_id) for item_id in item_ids)
    return [
        AffectedItemEntry(
            key=row.key,
            state=row.state,
            parent=book.item_key(row.parent_id),
            version=row.version,
        )
        for row in rows
        if row is not None
    ]


def register(server: MCPServer) -> None:
    """
    Add item_update to a server.

    Args:
        - server (MCPServer): the server.
    """
    server.add_tool(
        item_update,
        description=describe(
            "Change an item's title, body, state, parent or references, passing "
            "expected_version from your last read. Take state names from the "
            "workflow in brief_get. Send a parent change, or a "
            "drop of an item with children, alone. On an item with children "
            "those two first return a plan and a confirm_token and write "
            "nothing else; call again with the same arguments plus the token."
        ),
        annotations=DESTRUCTIVE,
    )
