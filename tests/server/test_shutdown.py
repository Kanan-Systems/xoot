"""
SIGINT and SIGTERM stop the server within two seconds, without a traceback.

Drives a raw subprocess: the signal has to reach the server process itself,
which the SDK's stdio client does not expose.
"""

import json
import select
import signal
import subprocess
import time
from collections.abc import Callable
from typing import IO

import pytest

WAIT_S = 30.0
STOP_S = 2.0


def _readable(stream: IO[bytes], timeout: float) -> bool:
    ready, _, _ = select.select([stream], [], [], timeout)
    return bool(ready)


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_signal_stops_the_server_cleanly(
    raw_server: Callable[[], subprocess.Popen[bytes]],
    raw_initialize: bytes,
    signum: signal.Signals,
) -> None:
    """A signal mid-session ends the process promptly, exit 0, no traceback."""
    with raw_server() as server:
        assert server.stdin and server.stdout and server.stderr
        # An initialize reply means the server is serving, so its signal
        # handlers are already in place.
        server.stdin.write(raw_initialize)
        server.stdin.flush()
        assert _readable(server.stdout, WAIT_S), "no initialize reply"
        assert json.loads(server.stdout.readline())["id"] == 1

        started = time.monotonic()
        server.send_signal(signum)
        try:
            code = server.wait(timeout=STOP_S)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
            pytest.fail(f"server still running {STOP_S}s after {signum.name}")
        elapsed = time.monotonic() - started
        stderr = server.stderr.read().decode()

    assert code == 0, stderr
    assert elapsed < STOP_S
    assert "Traceback" not in stderr
    assert f"stopping on {signum.name}" in stderr
