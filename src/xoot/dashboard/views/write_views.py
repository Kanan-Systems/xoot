"""
Write operations: each resolves the path's project and keys, calls the same
service function as the MCP tool, and renders the same output model.

Two-phase writes follow the MCP flow. A move, or a drop of an item that has
children, and every push first return a plan and a confirm_token; the same
body plus the token applies it. The token is bound to the dashboard tool,
the call's canonical arguments, the plan and the dashboard actor, so a token
issued to an MCP client is refused here and the other way round.
"""

import sqlite3
from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel

from xoot.dashboard.api_error import ApiError
from xoot.dashboard.requests.capture_request import CaptureRequest
from xoot.dashboard.requests.cover_request import CoverRequest
from xoot.dashboard.requests.decision_create_request import DecisionCreateRequest
from xoot.dashboard.requests.decision_update_request import DecisionUpdateRequest
from xoot.dashboard.requests.item_create_request import ItemCreateRequest
from xoot.dashboard.requests.item_update_request import ItemUpdateRequest
from xoot.dashboard.requests.move_request import MoveRequest
from xoot.dashboard.requests.project_rename_request import ProjectRenameRequest
from xoot.dashboard.requests.push_request import PushRequest
from xoot.dashboard.schemas.project_info import ProjectInfo
from xoot.dashboard.views.lookup import decision_of, item_of, project_of
from xoot.dashboard.views.project_views import project_info
from xoot.dashboard.write_errors import CONFLICT
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.decision.decision_update import DecisionUpdate
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item_change import ItemChange
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.repositories.item import item_db
from xoot.server.confirm import args_digest, confirmation
from xoot.server.key_book import KeyBook
from xoot.server.render import (
    change_entry,
    completion,
    decision_detail,
    item_detail,
    item_summary,
    item_write_output,
)
from xoot.server.schemas.affected_item_entry import AffectedItemEntry
from xoot.server.schemas.cover_output import CoverOutput
from xoot.server.schemas.decision_write_output import DecisionOutput
from xoot.server.schemas.item_update_output import ItemUpdateOutput
from xoot.server.schemas.item_write_output import ItemWriteOutput
from xoot.server.schemas.literals import Phase
from xoot.server.schemas.push_output import PushOutput
from xoot.server.schemas.subtree_output import SubtreeOutput
from xoot.server.subtree_change import SubtreeChange, plan_output
from xoot.services import update_paths
from xoot.services.backlog_push_service import apply_push, preview_push
from xoot.services.backlog_service import capture, cover
from xoot.services.confirm_service import issue_token
from xoot.services.decision_service import create_decision, update_decision
from xoot.services.item_service import create_item, update_item_in
from xoot.services.project_service import overview, rename_project
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store

# Token tools of the dashboard; distinct from the MCP tool names.
UPDATE_TOOL = "dashboard_item_update"
MOVE_TOOL = "dashboard_item_move"
PUSH_TOOL = "dashboard_backlog_push"
PREVIEW_REQUIRED = "the item now has children; preview the change first"

type Work[M: BaseModel] = Callable[[Store], M]


def create_item_work(
    prefix: str, request: ItemCreateRequest, write: WriteContext
) -> Work[ItemWriteOutput]:
    """Create a goal, batch or subtask (item_service.create_item)."""

    def work(store: Store) -> ItemWriteOutput:
        with store.read() as conn:
            project = project_of(conn, prefix)
            parent_id = _optional_item_id(conn, project, request.parent)
        create = ItemCreate(
            kind=ItemKind(request.kind),
            title=request.title,
            body=request.body,
            parent_id=parent_id,
        )
        item, report = create_item(store, project.id, create, write)
        with store.read() as conn:
            return item_write_output(conn, project, item, report)

    return work


def capture_work(
    prefix: str, request: CaptureRequest, write: WriteContext
) -> Work[ItemWriteOutput]:
    """Capture a backlog item (backlog_service.capture)."""

    def work(store: Store) -> ItemWriteOutput:
        with store.read() as conn:
            project = project_of(conn, prefix)
            found_on = item_of(conn, project, request.found_on)
        draft = ItemDraft(title=request.title, body=request.body)
        item, report = capture(store, project.id, found_on.id, draft, write)
        with store.read() as conn:
            return item_write_output(conn, project, item, report)

    return work


def update_item_work(
    prefix: str, key: str, request: ItemUpdateRequest, write: WriteContext
) -> Work[ItemUpdateOutput]:
    """
    Change title, body or state (item_service.update_item_in); a drop of an
    item with children goes through the two-phase subtree drop.
    """
    fields = request.model_dump(
        exclude_unset=True, exclude={"expected_version", "confirm_token"}
    )
    digest = _digest(request, prefix=prefix, key=key)

    def work(store: Store) -> ItemUpdateOutput:
        with store.read() as conn:
            project = project_of(conn, prefix)
            item = item_of(conn, project, key)
            mode, children = update_paths.choose_path(
                conn, item, set(fields), fields.get("state")
            )
        if mode == "update":
            return _direct_update(store, project, item.id, request, fields, write)
        change = SubtreeChange(
            mode="drop",
            project=project.key_prefix,
            item_id=item.id,
            key=item.key,
            new_parent_id=None,
            state=fields["state"],
            expected_version=request.expected_version,
            write=write,
        )
        return _subtree(store, project, change, children, request.confirm_token, digest)

    return work


def move_work(
    prefix: str, request: MoveRequest, write: WriteContext
) -> Work[ItemUpdateOutput]:
    """Reparent an item with its subtree (subtree_service.apply_reparent)."""
    digest = _digest(request, prefix=prefix)

    def work(store: Store) -> ItemUpdateOutput:
        with store.read() as conn:
            project = project_of(conn, prefix)
            item = item_of(conn, project, request.key)
            parent = item_of(conn, project, request.parent)
            _, children = update_paths.choose_path(conn, item, {"parent"}, None)
        change = SubtreeChange(
            mode="reparent",
            project=project.key_prefix,
            item_id=item.id,
            key=item.key,
            new_parent_id=parent.id,
            state=None,
            expected_version=request.expected_version,
            write=write,
        )
        return _subtree(
            store, project, change, children, request.confirm_token, digest, MOVE_TOOL
        )

    return work


def cover_work(
    prefix: str, request: CoverRequest, write: WriteContext
) -> Work[CoverOutput]:
    """Cover a backlog item with a subtask (backlog_service.cover)."""

    def work(store: Store) -> CoverOutput:
        with store.read() as conn:
            project = project_of(conn, prefix)
            backlog_id = item_of(conn, project, request.key).id
            batch_id = _optional_item_id(conn, project, request.batch)
        subtask, closed, report = cover(store, backlog_id, batch_id, write)
        with store.read() as conn:
            book = KeyBook(conn)
            return CoverOutput(
                project=project.key_prefix,
                subtask=item_detail(book, subtask),
                backlog=item_summary(book, closed),
                **completion(report),
            )

    return work


def push_work(
    prefix: str, request: PushRequest, write: WriteContext
) -> Work[PushOutput]:
    """Push a backlog item one level up, always two-phase (apply_push)."""
    digest = _digest(request, prefix=prefix)

    def work(store: Store) -> PushOutput:
        with store.read() as conn:
            project = project_of(conn, prefix)
            item_id = item_of(conn, project, request.key).id
        if request.confirm_token is None:
            plan = preview_push(store, item_id)
            token = issue_token(
                store,
                project.id,
                PUSH_TOOL,
                digest,
                plan.plan_sha256,
                actor=write.actor,
            )
            return _push_output(store, project, plan.root_id, plan.changes, token)
        claim = confirmation(PUSH_TOOL, request.confirm_token, digest)
        plan, report = apply_push(store, item_id, write, claim)
        output = _push_output(store, project, plan.root_id, plan.changes, None)
        return output.model_copy(update=completion(report))

    return work


def create_decision_work(
    prefix: str, request: DecisionCreateRequest, write: WriteContext
) -> Work[DecisionOutput]:
    """Record a decision (decision_service.create_decision)."""

    def work(store: Store) -> DecisionOutput:
        with store.read() as conn:
            project = project_of(conn, prefix)
            owner_id = item_of(conn, project, request.owner).id
            supersedes_id = (
                None
                if request.supersedes is None
                else decision_of(conn, project, request.supersedes).id
            )
        create = DecisionCreate(
            owner_item_id=owner_id,
            title=request.title,
            body=request.body,
            status=request.status,
            supersedes_id=supersedes_id,
        )
        decision = create_decision(store, project.id, create, write)
        with store.read() as conn:
            detail = decision_detail(KeyBook(conn), decision)
        return DecisionOutput(project=project.key_prefix, decision=detail)

    return work


def update_decision_work(
    prefix: str, key: str, request: DecisionUpdateRequest, write: WriteContext
) -> Work[DecisionOutput]:
    """Change a decision (decision_service.update_decision)."""

    def work(store: Store) -> DecisionOutput:
        with store.read() as conn:
            project = project_of(conn, prefix)
            decision = decision_of(conn, project, key)
        update = DecisionUpdate(
            **request.model_dump(exclude_unset=True, exclude={"expected_version"})
        )
        stored = update_decision(
            store, decision.id, request.expected_version, update, write
        )
        with store.read() as conn:
            detail = decision_detail(KeyBook(conn), stored)
        return DecisionOutput(project=project.key_prefix, decision=detail)

    return work


def rename_project_work(
    prefix: str, request: ProjectRenameRequest, write: WriteContext
) -> Work[ProjectInfo]:
    """Rename a project or add an alias (project_service.rename_project)."""

    def work(store: Store) -> ProjectInfo:
        with store.read() as conn:
            project_id = project_of(conn, prefix).id
        rename_project(store, project_id, request.name, request.alias, write)
        with store.read() as conn:
            return project_info(overview(conn, project_of(conn, prefix)))

    return work


def _digest(request: BaseModel, **path: str) -> str:
    """The call's canonical arguments: path values plus the body, token excluded."""
    body = request.model_dump(
        mode="json", exclude_unset=True, exclude={"confirm_token"}
    )
    return args_digest({**path, **body})


def _optional_item_id(
    conn: sqlite3.Connection, project: Project, key: str | None
) -> int | None:
    return None if key is None else item_of(conn, project, key).id


# Six arguments: the call's store, project, item, request, fields and actor.
def _direct_update(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    store: Store,
    project: Project,
    item_id: int,
    request: ItemUpdateRequest,
    fields: dict[str, Any],
    write: WriteContext,
) -> ItemUpdateOutput:
    """Apply an update chosen without a preview, unless it now drops a parent."""
    with store.write() as conn:
        item = item_db.get(conn, item_id)
        if (
            item is not None
            and update_paths.drops(conn, item, fields.get("state"))
            and update_paths.has_children(conn, item)
        ):
            raise ApiError(CONFLICT, "PreviewRequired", PREVIEW_REQUIRED)
        scope = WriteScope(conn, write)
        updated = update_item_in(
            scope, item_id, request.expected_version, ItemUpdate(**fields)
        )
        report = scope.report()
    with store.read() as conn:
        detail = item_detail(KeyBook(conn), updated)
    return ItemUpdateOutput(
        **completion(report),
        item=detail,
        plan=None,
        mode="update",
        phase="applied",
        project=project.key_prefix,
        confirm_token=None,
    )


# Seven arguments: the change, where it runs, and its two-phase inputs.
def _subtree(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    store: Store,
    project: Project,
    change: SubtreeChange,
    children: bool,
    token: str | None,
    digest: str,
    tool: str = UPDATE_TOOL,
) -> ItemUpdateOutput:
    """A drop or move: direct when childless, else preview then apply."""
    if not children:
        with store.write() as conn:
            root = item_db.get(conn, change.item_id)
            if root is not None and update_paths.has_children(conn, root):
                raise ApiError(CONFLICT, "PreviewRequired", PREVIEW_REQUIRED)
            scope = WriteScope(conn, change.write)
            plan = change.apply_in(scope)
            report = scope.report()
        return plan_output(store, change, "applied", None, plan, report)
    if token is None:
        plan = change.preview(store)
        issued = issue_token(
            store, project.id, tool, digest, plan.plan_sha256, actor=change.write.actor
        )
        return plan_output(store, change, "preview", issued, plan)
    plan, report = change.apply(store, confirmation(tool, token, digest))
    return plan_output(store, change, "applied", None, plan, report)


def _push_output(
    store: Store,
    project: Project,
    root_id: int,
    changes: Sequence[ItemChange],
    token: str | None,
) -> PushOutput:
    """Render a push plan; an applied one also carries the item as it now stands."""
    with store.read() as conn:
        book = KeyBook(conn)
        root = item_db.get(conn, root_id)
        item = None
        if token is None and root is not None:
            item = AffectedItemEntry(
                key=root.key,
                state=root.state,
                parent=book.item_key(root.parent_id),
                version=root.version,
            )
        plan = SubtreeOutput(
            root="" if root is None else root.key,
            changes=[change_entry(book, change) for change in changes],
        )
        phase: Phase = "preview" if token is not None else "applied"
        return PushOutput(
            item=item,
            plan=plan,
            phase=phase,
            project=project.key_prefix,
            confirm_token=token,
        )
