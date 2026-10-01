"""
xoot-mcp refuses an unsafe database path at startup, with the line and exit
code `xoot dashboard` gives, and serves nothing.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from xoot.cli import exit_codes
from xoot.cli.__main__ import main as cli_main

EXIT_TIMEOUT_S = 30.0
# Inside the range this test suite may use; the refusal comes before binding.
PORT = "7381"


def _unsafe(db_path: Path) -> Path:
    db_path.parent.mkdir()
    db_path.parent.chmod(0o750)
    return db_path


def test_server_exits_at_startup_like_the_dashboard(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 3 with stdin still open; the same stderr line; nothing created."""
    _unsafe(db_path)
    with subprocess.Popen(
        [sys.executable, "-m", "xoot.server", "--db", str(db_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as server:
        code = server.wait(timeout=EXIT_TIMEOUT_S)
        assert server.stdout and server.stderr
        out, err = server.stdout.read(), server.stderr.read().decode()
    assert code == exit_codes.UNAVAILABLE
    assert out == b""
    assert cli_main(["--db", str(db_path), "dashboard", "--port", PORT]) == 3
    dashboard_err = capsys.readouterr().err
    assert err == dashboard_err
    assert err.startswith("error: UnsafePathError: refusing to open ")
    assert "group or other permissions (mode 0750)" in err
    assert not db_path.exists()
