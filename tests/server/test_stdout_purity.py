"""
stdout carries protocol messages only.

This drives a raw subprocess rather than the SDK client, which cannot observe
stdout before it sends initialize.
"""

import json
import select
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any

from mcp.types import jsonrpc_message_adapter

from xoot.models.project.project import Project

WAIT_S = 30.0
QUIET_S = 1.0

REQUESTS: list[dict[str, Any]] = [
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "brief_get", "arguments": {"project": "xo"}},
    },
    {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "item_get", "arguments": {"key": "xoot-99"}},
    },
]


def _readable(stream: IO[bytes], timeout: float) -> bool:
    ready, _, _ = select.select([stream], [], [], timeout)
    return bool(ready)


def test_stdout_is_protocol_only(
    db_path: Path,
    project: Project,
    raw_server: Callable[[], subprocess.Popen[bytes]],
    raw_initialize: bytes,
) -> None:
    """Nothing reaches stdout before initialize; afterwards every line is JSON-RPC."""
    assert project.key_prefix == "xoot"
    with raw_server() as server:
        assert server.stdin and server.stdout and server.stderr
        assert _readable(server.stderr, WAIT_S), "server did not start"
        assert f"database: {db_path}".encode() in server.stderr.readline()
        assert not _readable(server.stdout, QUIET_S), "stdout written before initialize"

        lines_in = [raw_initialize]
        lines_in.extend(json.dumps(request).encode() + b"\n" for request in REQUESTS)
        for line_in in lines_in:
            server.stdin.write(line_in)
            server.stdin.flush()
        lines, answered = [], set()
        while answered != {1, 2, 3, 4}:
            assert _readable(server.stdout, WAIT_S), f"no reply after {answered}"
            line = server.stdout.readline()
            assert line, "stdout closed early"
            lines.append(line)
            message = json.loads(line)
            if "id" in message:
                answered.add(message["id"])
        server.stdin.close()
        lines.extend(server.stdout.read().splitlines(keepends=True))
        assert server.wait(timeout=WAIT_S) == 0

    for line in lines:
        jsonrpc_message_adapter.validate_json(line)
    messages = [json.loads(line) for line in lines]
    replies = {message["id"]: message for message in messages if "id" in message}
    assert replies[3]["result"]["isError"] is False
    assert replies[4]["result"]["isError"] is True
