"""
Fixtures for the end-to-end server tests.

Every test spawns `python -m xoot.server --db <tmp>` and drives it through
the SDK's own stdio client, so the protocol, argument validation and error
paths are the real ones. Projects are registered through the services before
the server starts; the server's stderr is kept in a file per test. Tests
that must see raw stdio or signal the process use raw_server instead.
"""

import json
import subprocess
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.client.context import ClientRequestContext
from mcp.types import Implementation, ListRootsResult, Root

type Scenario = Callable[[ClientSession], Awaitable[Any]]
type RawServer = Callable[[], subprocess.Popen[bytes]]

DEFAULT_CLIENT = "claude-code"


class Harness:
    """
    Spawns the server on the test database and calls its tools.

    run() starts one server process per call. roots=None declares no roots
    capability; a list declares it and answers roots/list with those URIs.
    cwd is the server process's working directory.
    """

    def __init__(self, db_path: Path, stderr: Path) -> None:
        """
        Bind the harness to a database and a stderr log.

        Args:
            - db_path (Path): the database the server opens.
            - stderr (Path): the file the server's stderr is appended to.
        """
        self.db_path = db_path
        self.stderr = stderr

    def run(
        self,
        scenario: Scenario,
        *,
        cwd: Path | None = None,
        roots: list[str] | None = None,
        client_name: str = DEFAULT_CLIENT,
    ) -> Any:
        """
        Spawn the server, initialize a client session and run a scenario.

        Args:
            - scenario (Scenario): what to do with the session.
            - cwd (Path | None): the server's working directory.
            - roots (list[str] | None): root URIs, or None for no capability.
            - client_name (str): the client_info name sent at initialize.

        Returns:
            - result (Any): what the scenario returned.
        """
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "xoot.server", "--db", str(self.db_path)],
            cwd=cwd,
        )

        async def list_roots(_context: ClientRequestContext) -> ListRootsResult:
            return ListRootsResult(roots=[Root(uri=uri) for uri in roots or []])

        async def main() -> Any:
            with self.stderr.open("a", encoding="utf-8") as errlog:
                async with stdio_client(params, errlog=errlog) as (read, write):
                    async with ClientSession(
                        read,
                        write,
                        list_roots_callback=None if roots is None else list_roots,
                        client_info=Implementation(name=client_name, version="9.9.9"),
                    ) as client:
                        await client.initialize()
                        return await scenario(client)

        return anyio.run(main)

    @staticmethod
    async def ok(client: ClientSession, name: str, /, **arguments: Any) -> Any:
        """
        Call a tool, require success and return its structured content.

        Args:
            - client (ClientSession): the session.
            - name (str): the tool.
            - arguments (Any): the tool's arguments.

        Returns:
            - content (Any): the structured result.
        """
        result = await client.call_tool(name, arguments)
        assert not result.is_error, result.content
        return result.structured_content

    @staticmethod
    async def error(client: ClientSession, name: str, /, **arguments: Any) -> str:
        """
        Call a tool, require a tool error and return its message.

        Args:
            - client (ClientSession): the session.
            - name (str): the tool.
            - arguments (Any): the tool's arguments.

        Returns:
            - message (str): the error text.
        """
        result = await client.call_tool(name, arguments)
        assert result.is_error, result.structured_content
        return result.content[0].text


@pytest.fixture(name="server_stderr")
def fixture_server_stderr(tmp_path: Path) -> Path:
    """The file the spawned servers' stderr is appended to."""
    return tmp_path / "server-stderr.log"


@pytest.fixture(name="harness")
def fixture_harness(db_path: Path, server_stderr: Path) -> Harness:
    """A harness on this test's database."""
    return Harness(db_path, server_stderr)


@pytest.fixture(name="raw_server")
def fixture_raw_server(db_path: Path) -> RawServer:
    """Factory: spawn the server on this test's database with piped stdio."""

    def spawn() -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            [sys.executable, "-m", "xoot.server", "--db", str(db_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    return spawn


@pytest.fixture(name="raw_initialize")
def fixture_raw_initialize() -> bytes:
    """An initialize request with id 1, as one newline-terminated JSON-RPC line."""
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "raw-test", "version": "1"},
        },
    }
    return json.dumps(request).encode() + b"\n"
