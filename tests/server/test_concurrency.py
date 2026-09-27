"""S8: concurrent calls each get their own Store on their own worker thread."""

from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession

from xoot.models.project.project import Project

CALLS = 20


def test_concurrent_calls_share_no_connection(
    project: Project,
    server_stderr: Path,
    harness: Any,
) -> None:
    """20 overlapping reads and writes all succeed, with no cross-thread sqlite use."""
    assert project.key_prefix == "xoot"

    async def scenario(client: ClientSession) -> list[Any]:
        started = await harness.ok(client, "session_start", project="xo", title="t")
        key = started["session"]["key"]
        results: list[Any] = []

        async def one(n: int) -> None:
            if n % 2:
                results.append(await harness.ok(client, "brief_get", project="xo"))
            else:
                results.append(
                    await harness.ok(client, "capture", session=key, title=f"side {n}")
                )

        async with anyio.create_task_group() as group:
            for n in range(CALLS):
                group.start_soon(one, n)
        return results

    results = harness.run(scenario)
    assert len(results) == CALLS
    captured = {r["key"] for r in results if "key" in r}
    assert len(captured) == CALLS // 2
    log = server_stderr.read_text(encoding="utf-8")
    assert "ProgrammingError" not in log
    assert "Traceback" not in log
