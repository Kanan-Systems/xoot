"""Session tools: session_start and session_close."""

from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.fields import Body, Title
from xoot.models.session.disposition import Disposition
from xoot.models.session.session_close import MAX_DISPOSITIONS, SessionClose
from xoot.models.session.session_close_plan import SessionClosePlan
from xoot.models.session.session_start import MAX_FOCUS_ITEMS, SessionStart
from xoot.server.clients import client_info, session_client
from xoot.server.confirm import args_digest, confirmation
from xoot.server.db_call import run_db
from xoot.server.key_book import KeyBook
from xoot.server.render import change_entry, item_summary, session_summary
from xoot.server.resolution import item_by_key, resolve_project, session_writer
from xoot.server.roots import root_paths
from xoot.server.schemas.arguments import ConfirmToken, ProjectAlias, SessionKey
from xoot.server.schemas.auto_backlog_warning_entry import AutoBacklogWarningEntry
from xoot.server.schemas.close_preview import ClosePreview, CloseWarningItem
from xoot.server.schemas.close_warning_entry import CloseWarningEntry
from xoot.server.schemas.focus_warning_entry import FocusWarningEntry
from xoot.server.schemas.session_close_output import SessionCloseOutput
from xoot.server.schemas.session_start_output import SessionStartOutput
from xoot.server.tool_meta import DESTRUCTIVE, RESOLUTION, WRITE, describe
from xoot.services.confirm_service import issue_token
from xoot.services.session_close_service import close_session, preview_close
from xoot.services.session_service import start_session
from xoot.store.store import Store

CLOSE_TOOL = "session_close"


async def session_start(
    ctx: Context,
    title: Title,
    project: ProjectAlias = None,
    focus: Annotated[
        list[str] | None,
        Field(max_length=MAX_FOCUS_ITEMS, description="Item keys to work on."),
    ] = None,
) -> SessionStartOutput:
    """
    Open a session in a project and link its focus items.

    Args:
        - ctx (Context): the request context.
        - title (str): the session title.
        - project (str | None): an alias; resolved from roots or cwd if None.
        - focus (list[str] | None): item keys the session means to work on.

    Returns:
        - output (SessionStartOutput): the session, pending backlog, warnings.
    """
    roots = await root_paths(ctx, project)
    info = client_info(ctx)
    actor = Actor(kind=ActorKind.CLAUDE, client=session_client(info))

    def work(store: Store) -> SessionStartOutput:
        found, resolved_by = resolve_project(store, project, roots)
        with store.read() as conn:
            focus_ids = tuple(item_by_key(conn, key).id for key in focus or ())
        request = SessionStart(title=title, focus_item_ids=focus_ids)
        result = start_session(store, found.id, request, actor)
        with store.read() as conn:
            book = KeyBook(conn)
            warnings = [
                FocusWarningEntry(
                    key=warning.key,
                    open_sessions=[
                        key
                        for key in map(book.session_key, warning.open_session_ids)
                        if key is not None
                    ],
                )
                for warning in result.warnings
            ]
            return SessionStartOutput(
                project=found.key_prefix,
                resolved_by=resolved_by,
                session=session_summary(book, result.session),
                client_info=info,
                pending=[item_summary(book, item) for item in result.pending],
                warnings=warnings,
            )

    return await run_db(ctx, work)


async def session_close(
    ctx: Context,
    session: SessionKey,
    dispositions: Annotated[
        dict[str, Disposition],
        Field(
            max_length=MAX_DISPOSITIONS,
            description=(
                "Item key to disposition for every open item linked to the "
                "session: carry_over, session_backlog, project_backlog or dropped."
            ),
        ),
    ],
    summary: Body | None = None,
    confirm_token: ConfirmToken = None,
) -> SessionCloseOutput:
    """
    Close a session, previewing the dispositions first.

    Args:
        - ctx (Context): the request context.
        - session (str): the open session key.
        - dispositions (dict[str, Disposition]): item key to disposition.
        - summary (str | None): what the session did.
        - confirm_token (str | None): the preview's token, to apply.

    Returns:
        - output (SessionCloseOutput): the preview and a token, or the session.

    Raises:
        - ToolError: a required item has no disposition; the message lists
          the missing item keys.
    """
    digest = args_digest(
        {
            "session": session,
            "dispositions": {k: v.value for k, v in dispositions.items()},
            "summary": summary,
        }
    )

    def work(store: Store) -> SessionCloseOutput:
        found, write = session_writer(store, session)
        with store.read() as conn:
            by_id = {item_by_key(conn, k).id: v for k, v in dispositions.items()}
        request = SessionClose(summary=summary, dispositions=by_id)
        if confirm_token is None:
            plan = preview_close(store, found.id, request)
            if plan.missing_item_ids:
                raise ToolError(_missing_message(store, plan))
            token = issue_token(store, found.id, CLOSE_TOOL, digest, plan.plan_sha256)
            return SessionCloseOutput(
                phase="preview",
                confirm_token=token,
                preview=_preview(store, plan),
                session=None,
            )
        claim = confirmation(CLOSE_TOOL, confirm_token, digest)
        closed = close_session(store, found.id, request, write.actor, claim)
        with store.read() as conn:
            summary_out = session_summary(KeyBook(conn), closed)
        return SessionCloseOutput(
            phase="applied", confirm_token=None, preview=None, session=summary_out
        )

    return await run_db(ctx, work)


def _missing_message(store: Store, plan: SessionClosePlan) -> str:
    # Keys come from stored rows, never from the caller, so they are safe to echo.
    with store.read() as conn:
        keys = _keys(KeyBook(conn), plan.missing_item_ids)
    return f"missing dispositions: {', '.join(keys)}"


def _preview(store: Store, plan: SessionClosePlan) -> ClosePreview:
    with store.read() as conn:
        book = KeyBook(conn)
        keyed = {
            book.item_key(item_id): disposition
            for item_id, disposition in plan.dispositions.items()
        }
        warnings: list[CloseWarningItem] = [
            CloseWarningEntry(
                key=w.key, parent=w.parent_key, parent_category=w.parent_category
            )
            for w in plan.warnings
        ]
        warnings.extend(
            AutoBacklogWarningEntry(
                key=c.key,
                origin_session=book.session_key(c.before.get("backlog_session_id")),
            )
            for c in plan.auto_backlog
        )
        return ClosePreview(
            required=_keys(book, plan.required_item_ids),
            dispositions={k: v for k, v in keyed.items() if k is not None},
            changes=[change_entry(book, c) for c in plan.changes],
            auto_backlog=[change_entry(book, c) for c in plan.auto_backlog],
            warnings=warnings,
        )


def _keys(book: KeyBook, item_ids: tuple[int, ...]) -> list[str]:
    return [key for key in map(book.item_key, item_ids) if key is not None]


def register(server: MCPServer) -> None:
    """
    Add the session tools to a server.

    Args:
        - server (MCPServer): the server.
    """
    server.add_tool(
        session_start,
        description=describe(
            "Start a working session in a project; call it first. Links the "
            "focus items and returns the session key every write needs, plus "
            "backlog items earlier sessions left and focus items other open "
            f"sessions share. {RESOLUTION}"
        ),
        annotations=WRITE,
    )
    server.add_tool(
        session_close,
        description=describe(
            "Close the session; never skip it. Every open item linked to the "
            "session needs a disposition; a call missing any fails and lists "
            "the missing item keys. First call returns the plan, warnings and "
            "a confirm_token, and writes nothing else; call again with the same "
            "arguments plus the token. The warnings include every item the "
            "close moves from an earlier session's backlog to the project "
            "backlog. Before confirming, name every auto-backlog warning to "
            "the user and get their agreement."
        ),
        annotations=DESTRUCTIVE,
    )
