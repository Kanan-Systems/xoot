"""Decision tools: decisions_list, decision_get, decision_record and decision_update."""

from typing import Annotated, Literal

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from xoot.models.decision.decision import Decision
from xoot.models.decision.decision_changes_input import DecisionChangesInput
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.decision.decision_update import DecisionUpdate
from xoot.models.fields import Body, Title
from xoot.models.project.project import Project
from xoot.repositories.decision import decision_db
from xoot.server.clients import write_context
from xoot.server.db_call import run_db
from xoot.server.key_book import KeyBook
from xoot.server.render import decision_detail, decision_summary
from xoot.server.resolution import decision_by_key, item_by_key, resolve_project
from xoot.server.roots import root_paths
from xoot.server.schemas.arguments import (
    DecisionKey,
    ExpectedVersion,
    ItemKey,
    ProjectAlias,
)
from xoot.server.schemas.decision_write_output import DecisionOutput
from xoot.server.schemas.decisions_output import DecisionsOutput
from xoot.server.tool_meta import READ, RESOLUTION, WRITE, describe
from xoot.services.decision_service import create_decision, update_decision
from xoot.store.store import Store
from xoot.utils.keys import KEY_MAX

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


async def decision_get(
    ctx: Context, key: DecisionKey, project: ProjectAlias = None
) -> DecisionOutput:
    """
    Return one decision with its body.

    Args:
        - ctx (Context): the request context.
        - key (str): the decision key.
        - project (str | None): an alias; resolved from the key, roots or cwd.

    Returns:
        - output (DecisionOutput): the decision.
    """
    roots = await root_paths(ctx, project)

    def work(store: Store) -> DecisionOutput:
        found, _ = resolve_project(store, project, roots, [key])
        with store.read() as conn:
            return _output(KeyBook(conn), found, decision_by_key(conn, found, key))

    return await run_db(ctx, work)


# One parameter per tool argument: the SDK derives the input schema from it.
async def decision_record(  # pylint: disable=too-many-arguments
    ctx: Context,
    *,
    owner: Annotated[
        ItemKey,
        Field(description="The goal, batch or subtask the decision was made on."),
    ],
    title: Title,
    body: Body,
    project: ProjectAlias = None,
    status: Literal["locked", "deferred"] = "locked",
    supersedes: Annotated[
        str | None,
        Field(
            max_length=KEY_MAX,
            description=(
                "Key of a decision of the same goal that this one replaces; it "
                "becomes superseded. A decision is superseded at most once."
            ),
        ),
    ] = None,
) -> DecisionOutput:
    """
    Record a decision on the item it was made on.

    Args:
        - ctx (Context): the request context.
        - owner (str): the goal, batch or subtask key.
        - title (str): the decision title.
        - body (str): the decision and its reasons.
        - project (str | None): an alias; resolved from keys, roots or cwd.
        - status (str): locked or deferred.
        - supersedes (str | None): the decision key it replaces.

    Returns:
        - output (DecisionOutput): the new decision.
    """
    roots = await root_paths(ctx, project)
    write = write_context(ctx)

    def work(store: Store) -> DecisionOutput:
        found, _ = resolve_project(store, project, roots, [owner, supersedes])
        with store.read() as conn:
            owner_id = item_by_key(conn, found, owner).id
            supersedes_id = (
                None
                if supersedes is None
                else decision_by_key(conn, found, supersedes).id
            )
        request = DecisionCreate(
            owner_item_id=owner_id,
            title=title,
            body=body,
            status=DecisionStatus(status),
            supersedes_id=supersedes_id,
        )
        decision = create_decision(store, found.id, request, write)
        with store.read() as conn:
            return _output(KeyBook(conn), found, decision)

    return await run_db(ctx, work)


async def decision_update(
    ctx: Context,
    key: DecisionKey,
    expected_version: ExpectedVersion,
    changes: DecisionChangesInput,
    project: ProjectAlias = None,
) -> DecisionOutput:
    """
    Change a decision's title, body or status.

    Args:
        - ctx (Context): the request context.
        - key (str): the decision key.
        - expected_version (int): the version the caller read.
        - changes (DecisionChangesInput): the fields to change.
        - project (str | None): an alias; resolved from the key, roots or cwd.

    Returns:
        - output (DecisionOutput): the stored decision.
    """
    roots = await root_paths(ctx, project)
    write = write_context(ctx)

    def work(store: Store) -> DecisionOutput:
        found, _ = resolve_project(store, project, roots, [key])
        with store.read() as conn:
            decision = decision_by_key(conn, found, key)
        update = DecisionUpdate(**changes.model_dump(exclude_unset=True))
        stored = update_decision(store, decision.id, expected_version, update, write)
        with store.read() as conn:
            return _output(KeyBook(conn), found, stored)

    return await run_db(ctx, work)


def _output(book: KeyBook, project: Project, decision: Decision) -> DecisionOutput:
    return DecisionOutput(
        project=project.key_prefix, decision=decision_detail(book, decision)
    )


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
            f"one status, each with the item it was made on. {RESOLUTION}"
        ),
        annotations=READ,
    )
    server.add_tool(
        decision_get,
        description=describe(
            f"One decision in full, body included, by its key. {RESOLUTION}"
        ),
        annotations=READ,
    )
    server.add_tool(
        decision_record,
        description=describe(
            "Record a decision (locked or deferred) on the goal, batch or "
            "subtask it was made on; its key is <owner key>/decision-<n>. "
            "supersedes names an older decision of the same goal, which "
            f"becomes superseded in the same write. {RESOLUTION}"
        ),
        annotations=WRITE,
    )
    server.add_tool(
        decision_update,
        description=describe(
            "Change a decision's title, body or status, passing expected_version "
            "from your last read. A superseded decision's status cannot change. "
            f"{RESOLUTION}"
        ),
        annotations=WRITE,
    )
