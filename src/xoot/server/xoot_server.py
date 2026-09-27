"""The MCPServer subclass that carries the database path and masks argument errors."""

from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp.types import CallToolResult, InputRequiredResult
from pydantic import ValidationError

from xoot.server.errors import safe_message


class XootServer(MCPServer):
    """
    An MCPServer bound to one database file.

    Tools read db_path from their Context to open a short-lived Store per
    call. call_tool rewrites the SDK's argument-validation error, whose text
    quotes the rejected input, into field locations only.
    """

    def __init__(self, db_path: Path, **kwargs: Any) -> None:
        """
        Create the server.

        Args:
            - db_path (Path): the database file every tool call opens.
            - kwargs (Any): passed to MCPServer.
        """
        super().__init__(**kwargs)
        self.db_path = db_path

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        context: Context[Any, Any] | None = None,
    ) -> CallToolResult | InputRequiredResult:
        """
        Call a tool, masking argument-validation details.

        Args:
            - name (str): the tool name.
            - arguments (dict[str, Any]): the raw arguments.
            - context (Context | None): the request context.

        Returns:
            - result (CallToolResult | InputRequiredResult): the SDK's result.

        Raises:
            - ToolError: the tool failed; for invalid arguments the message
              names field locations only.
        """
        try:
            return await super().call_tool(name, arguments, context)
        except UnexpectedToolError:
            raise
        except ToolError as exc:
            if isinstance(exc.__cause__, ValidationError):
                # Validation runs after the tool lookup, so name is a real tool.
                message = f"Error executing tool {name}: {safe_message(exc.__cause__)}"
                raise ToolError(message) from exc.__cause__
            raise
