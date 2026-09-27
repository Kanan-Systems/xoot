"""
The client's roots, as local paths.

Roots are requested only when a project-level call gives no alias and the
client declared the roots capability. A client that fails or stalls the
request is treated as having no usable roots, so resolution moves on to the
working directory instead of failing the call.
"""

from urllib.parse import unquote, urlsplit

import anyio
from mcp.server.mcpserver import Context
from mcp.shared.exceptions import MCPError
from pydantic import TypeAdapter, ValidationError

from xoot.models.fields import AbsolutePath

ROOTS_TIMEOUT_S = 5.0

_PATH = TypeAdapter(AbsolutePath)


async def root_paths(ctx: Context, alias: str | None) -> list[str]:
    """
    Fetch the client's file roots when resolution will need them.

    Args:
        - ctx (Context): the tool's request context.
        - alias (str | None): the call's explicit alias, if any.

    Returns:
        - paths (list[str]): normalized absolute paths; empty when an alias
          is given, the capability is missing, or the request fails, stalls
          or returns a malformed result.
    """
    capabilities = ctx.client_capabilities
    if alias is not None or capabilities is None or capabilities.roots is None:
        return []
    with anyio.move_on_after(ROOTS_TIMEOUT_S):
        try:
            result = await ctx.session.list_roots()
        except (MCPError, ValidationError):
            return []
        paths = (file_uri_path(str(root.uri)) for root in result.roots)
        return [path for path in paths if path is not None]
    return []


def file_uri_path(uri: str) -> str | None:
    """
    Turn a local file:// URI into a normalized absolute path.

    Args:
        - uri (str): a root URI.

    Returns:
        - path (str | None): the path, or None for another scheme, a remote
          host, or a path that is not a valid absolute path.
    """
    parts = urlsplit(uri)
    if parts.scheme != "file" or parts.netloc not in ("", "localhost"):
        return None
    try:
        return _PATH.validate_python(unquote(parts.path))
    except ValidationError:
        return None
