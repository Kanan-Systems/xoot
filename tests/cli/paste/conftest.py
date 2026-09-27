"""
Fixtures for the `xoot paste` CLI tests.

paste_cli runs main() in-process with a byte stdin and a stand-in for
/dev/tty: a file holding the answer, or a missing path for "no terminal",
so no test can ever block on the developer's real terminal. spawn runs
`python -m xoot.cli` in a new session, optionally with a pseudo-terminal as
its controlling terminal, for the tests that need a real one.
"""

import io
import json
import os
import pty
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from xoot.cli import console
from xoot.cli.__main__ import main

TIMEOUT_S = 60


@dataclass(frozen=True)
class PasteRun:
    """One CLI run: its exit code and both streams."""

    code: int
    out: str
    err: str

    def receipt(self) -> Any:
        """
        Parse the JSON inside the fenced receipt on stdout.

        Returns:
            - receipt (Any): the parsed receipt.
        """
        lines = self.out.strip().splitlines()
        assert lines[0] == "```xoot-receipt" and lines[-1] == "```"
        return json.loads("\n".join(lines[1:-1]))


@pytest.fixture(name="reply")
def fixture_reply() -> Callable[..., bytes]:
    """Factory: a chat reply, as bytes, holding one xoot block built from ops."""

    def build(ops: list[dict[str, Any]], **top: Any) -> bytes:
        block = {"xoot": 1, "project": "xo", **top, "ops": ops}
        return f"Sure:\n\n```xoot\n{json.dumps(block)}\n```\n".encode()

    return build


@pytest.fixture(name="paste_cli")
def fixture_paste_cli(
    db_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., PasteRun]:
    """Factory: run `xoot --db <test db> ARGS` with stdin bytes and a tty answer."""

    def run(*argv: str, stdin: bytes = b"", answer: str | None = None) -> PasteRun:
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(stdin)))
        tty = tmp_path / "tty"
        if answer is None:
            monkeypatch.setattr(console, "TTY_PATH", str(tmp_path / "no-tty"))
        else:
            tty.write_text(f"{answer}\n", encoding="utf-8")
            monkeypatch.setattr(console, "TTY_PATH", str(tty))
        code = main(["--db", str(db_path), *argv])
        captured = capsys.readouterr()
        return PasteRun(code, captured.out, captured.err)

    return run


@pytest.fixture(name="spawn")
def fixture_spawn(db_path: Path, tmp_path: Path) -> Callable[..., PasteRun]:
    """
    Factory: run the CLI as a real process in a new session. With answer
    set, a pseudo-terminal becomes its controlling terminal and the answer
    is typed into it; stdin carries the payload either way.
    """

    def run(*argv: str, stdin: bytes, answer: str | None) -> PasteRun:
        master, slave = pty.openpty()
        slave_path = os.ttyname(slave)

        def attach() -> None:
            # A session leader without a terminal acquires the first one it
            # opens; the fd itself may close, the session keeps the terminal.
            if answer is not None:
                os.open(slave_path, os.O_RDWR)

        env = {**os.environ, "XDG_DATA_HOME": str(tmp_path / "xdg")}
        try:
            # The test process runs no threads, so preexec_fn is safe here.
            with subprocess.Popen(  # pylint: disable=subprocess-popen-preexec-fn
                [sys.executable, "-m", "xoot.cli", "--db", str(db_path), *argv],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                preexec_fn=attach,
                env=env,
            ) as proc:
                if answer is not None:
                    os.write(master, f"{answer}\n".encode())
                out, err = proc.communicate(stdin, timeout=TIMEOUT_S)
        finally:
            os.close(master)
            os.close(slave)
        return PasteRun(proc.returncode, out.decode(), err.decode())

    return run
