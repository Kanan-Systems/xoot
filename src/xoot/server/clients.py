"""Mapping the connected MCP client to the actor every tool write records."""

from mcp.server.mcpserver import Context

from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client
from xoot.models.event.write_context import WriteContext
from xoot.server.schemas.client_info_entry import ClientInfoEntry

CODE_MARKER = "claude-code"


def client_info(ctx: Context) -> ClientInfoEntry | None:
    """
    Return the name and version the client sent at initialization.

    Args:
        - ctx (Context): the tool's request context.

    Returns:
        - info (ClientInfoEntry | None): the raw values, or None when the
          client sent none.
    """
    params = ctx.session.client_params
    if params is None:
        return None
    return ClientInfoEntry(
        name=params.client_info.name, version=params.client_info.version
    )


def write_context(ctx: Context) -> WriteContext:
    """
    Build the context of one tool write: Claude, through the mapped client.

    Mapped per call, so any number of conversations and clients can work on
    the same goal, each write labelled with its own client.

    Args:
        - ctx (Context): the tool's request context.

    Returns:
        - write (WriteContext): actor claude and client code or chat.
    """
    actor = Actor(kind=ActorKind.CLAUDE, client=map_client(client_info(ctx)))
    return WriteContext(actor=actor)


def map_client(info: ClientInfoEntry | None) -> Client:
    """
    Choose the client a write records.

    The name is self-reported and unauthenticated; it only labels the
    write, it grants nothing.

    Args:
        - info (ClientInfoEntry | None): the client's reported info.

    Returns:
        - client (Client): CODE when the name contains "claude-code" in any
          case, otherwise CHAT.
    """
    if info is not None and CODE_MARKER in info.name.lower():
        return Client.CODE
    return Client.CHAT
