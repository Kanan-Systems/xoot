"""Mapping the connected MCP client to the client recorded on a session."""

from mcp.server.mcpserver import Context

from xoot.models.session.client import Client
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


def session_client(info: ClientInfoEntry | None) -> Client:
    """
    Choose the client a new session records.

    The name is self-reported and unauthenticated; it only labels the
    session, it grants nothing.

    Args:
        - info (ClientInfoEntry | None): the client's reported info.

    Returns:
        - client (Client): CODE when the name contains "claude-code" in any
          case, otherwise CHAT.
    """
    if info is not None and CODE_MARKER in info.name.lower():
        return Client.CODE
    return Client.CHAT
