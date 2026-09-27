"""Decision tools: decisions_list, decision_record and decision_update."""

from typing import Annotated, Literal

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.decision.decision_update import DecisionUpdate
from xoot.models.fields import Body, Title
from xoot.repositories.decision import decision_db
from xoot.server.db_call import run_db
from xoot.server.key_book import KeyBook
from xoot.server.render import decision_detail, decision_summary
from xoot.server.resolution import (
    decision_by_key,
    optional_item_id,
    resolve_project,
    session_writer,
)
from xoot.server.roots import root_paths
from xoot.server.schemas.arguments import (
    DecisionKey,
    ExpectedVersion,
    ProjectAlias,
    SessionKey,
)
from xoot.server.schemas.decision_changes_input import DecisionChangesInput
from xoot.server.schemas.decision_detail import DecisionDetail
from xoot.server.schemas.decisions_output import DecisionsOutput
from xoot.server.tool_meta import READ, RESOLUTION, WRITE, describe
from xoot.services.decision_service import create_decision, update_decision
from xoot.store.store import Store

LIST_MAX = 50


async def decisions_list(
    ctx: Context,
    project: ProjectAlias = None,
    status: DecisionStatus | None = None,
) -> DecisionsOutput:
    """
    List a project's decisions, newest first.

    Args:
        - ctx (Context): the request context.
        - project (str | None): an alias; resolved from roots or cwd if None.
        - status (DecisionStatus | None): only this status.

    Returns:
        - output (DecisionsOutput): up to LIST_MAX decisions.
    """
    roots = await root_paths(ctx, project)

    def work(store: Store) -> DecisionsOutput:
        found, resolved_by = resolve_project(store, project, roots)
        with store.read() as conn:
            book = KeyBook(conn)
            rows = decision_db.list_recent(conn, found.id, status, LIST_MAX + 1)
            return DecisionsOutput(
                project=found.key_prefix,
                resolved_by=resolved_by,
                decisions=[decision_summary(book, d) for d in rows[:LIST_MAX]],
                truncated=len(rows) > LIST_MAX,
            )

    return await run_db(ctx, work)


# One parameter per tool argument: the SDK derives the input schema from it.
async def decision_record(  # pylint: disable=too-many-arguments
    ctx: Context,
    *,
    session: SessionKey,
    title: Title,
    body: Body,
    status: Literal["locked", "deferred"] = "locked",
    scope: Annotated[
        str | None, Field(description="Item key the decision applies to.")
    ] = None,
    supersedes: Annotated[
        str | None,
        Field(
            description=(
                "Key of a decision in the same project that this one replaces; "
                "it becomes superseded."
            )
        ),
    ] = None,
) -> DecisionDetail:
    """
    Record a decision in the session's project.

    Args:
        - ctx (Context): the request context.
        - session (str): the open session key.
        - title (str): the decision title.
        - body (str): the decision and its reasons.
        - status (str): locked or deferred.
        - scope (str | None): the item key it applies to.
        - supersedes (str | None): the decision key it replaces.

    Returns:
        - decision (DecisionDetail): the new decision.
    """

    def work(store: Store) -> DecisionDetail:
        found, write = session_writer(store, session)
        with store.read() as conn:
            scope_item_id = optional_item_id(conn, scope)
            supersedes_id = (
                None if supersedes is None else decision_by_key(conn, supersedes).id
            )
        request = DecisionCreate(
            title=title,
            body=body,
            status=DecisionStatus(status),
            supersedes_id=supersedes_id,
            scope_item_id=scope_item_id,
        )
        decision = create_decision(store, found.project_id, request, write)
        with store.read() as conn:
            return decision_detail(KeyBook(conn), decision)

    return await run_db(ctx, work)


async def decision_update(
    ctx: Context,
    session: SessionKey,
    key: DecisionKey,
    expected_version: ExpectedVersion,
    changes: DecisionChangesInput,
) -> DecisionDetail:
    """
    Change a decision's title, body or status.

    Args:
        - ctx (Context): the request context.
        - session (str): the open session key.
        - key (str): the decision key.
        - expected_version (int): the version the caller read.
        - changes (DecisionChangesInput): the fields to change.

    Returns:
        - decision (DecisionDetail): the stored decision.
    """

    def work(store: Store) -> DecisionDetail:
        _, write = session_writer(store, session)
        with store.read() as conn:
            decision = decision_by_key(conn, key)
        update = DecisionUpdate(**changes.model_dump(exclude_unset=True))
        stored = update_decision(store, decision.id, expected_version, update, write)
        with store.read() as conn:
            return decision_detail(KeyBook(conn), stored)

    return await run_db(ctx, work)


def register(server: MCPServer) -> None:
    """
    Add the decision tools to a server.

    Args:
        - server (MCPServer): the server.
    """
    server.add_tool(
        decisions_list,
        description=describe(
            "Decisions of a project, newest first, at most 50, optionally of "
            f"one status. {RESOLUTION}"
        ),
        annotations=READ,
    )
    server.add_tool(
        decision_record,
        description=describe(
            "Record a decision (locked or deferred) in the session's project, "
            "optionally scoped to one item. supersedes names an older decision "
            "of the same project; it becomes superseded in the same write."
        ),
        annotations=WRITE,
    )
    server.add_tool(
        decision_update,
        description=describe(
            "Change a decision's title, body or status, passing expected_version "
            "from your last read. A superseded decision cannot change."
        ),
        annotations=WRITE,
    )
