"""`xoot-mcp --version` prints the package version and never starts the server."""

import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

from xoot.server import __main__ as server_main

EXIT_TIMEOUT_S = 30.0


def test_version_exits_before_serving(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """main() exits 0 after printing, before the event loop would start."""

    def refuse(*_args: object) -> None:
        raise AssertionError("the server started")

    monkeypatch.setattr(server_main.anyio, "run", refuse)
    with pytest.raises(SystemExit) as exited:
        server_main.main(["--version"])
    assert exited.value.code == 0
    captured = capsys.readouterr()
    assert captured.out == f"xoot {version('xoot')}\n"
    assert captured.err == ""


def test_version_process_exits_with_stdin_open(tmp_path: Path, db_path: Path) -> None:
    """A real process exits on its own while stdin stays open: nothing serves."""
    with subprocess.Popen(
        [sys.executable, "-m", "xoot.server", "--db", str(db_path), "--version"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
    ) as server:
        code = server.wait(timeout=EXIT_TIMEOUT_S)
        assert server.stdout and server.stderr
        out, err = server.stdout.read(), server.stderr.read()
    assert code == 0
    assert out == f"xoot {version('xoot')}\n".encode()
    assert err == b""
    assert not db_path.exists()
