"""
Fixtures for the CLI tests: main() run in-process on the test database.

stdin is replaced per run, as a terminal only when an answer is given, and
XDG_DATA_HOME points into tmp_path, so no test can reach the user's data.
"""

import io
import json
import sqlite3
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from xoot.cli.__main__ import main
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.services.workflow_toml import dump_workflow

type Xoot = Callable[..., "Run"]

MARKER = "cli-secret-7d1f"


@dataclass(frozen=True)
class Run:
    """One main() call: its exit code and everything it printed."""

    code: int
    out: str
    err: str

    def json(self) -> Any:
        """
        Parse stdout as JSON.

        Returns:
            - value (Any): the parsed result.
        """
        return json.loads(self.out)


class FakeStdin(io.StringIO):
    """A stdin with a chosen answer that may claim to be a terminal."""

    def __init__(self, text: str, tty: bool) -> None:
        """
        Hold the answer text.

        Args:
            - text (str): what readline() returns.
            - tty (bool): what isatty() returns.
        """
        super().__init__(text)
        self.tty = tty

    def isatty(self) -> bool:
        """Report the chosen terminal status."""
        return self.tty


@pytest.fixture(name="private_xdg", autouse=True)
def fixture_private_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the default database location into tmp_path."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))


@pytest.fixture(name="xoot")
def fixture_xoot(
    db_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> Xoot:
    """Factory: run `xoot --db <test db> ARGS`, answering a prompt if given."""

    def run(*argv: str, answer: str | None = None) -> Run:
        text = "" if answer is None else f"{answer}\n"
        monkeypatch.setattr(sys, "stdin", FakeStdin(text, tty=answer is not None))
        code = main(["--db", str(db_path), *argv])
        captured = capsys.readouterr()
        return Run(code, captured.out, captured.err)

    return run


@pytest.fixture(name="secret_item")
def fixture_secret_item(project: Project, make_item: Callable[..., Item]) -> Item:
    """xoot-1: a goal whose title and body carry MARKER."""
    return make_item(project, ItemKind.GOAL, title=f"t {MARKER}", body=f"body {MARKER}")


@pytest.fixture(name="default_toml")
def fixture_default_toml(tmp_path: Path) -> Path:
    """The default workflow exported to a file."""
    path = tmp_path / "default.toml"
    path.write_text(dump_workflow(WorkflowDefinition.default()), encoding="utf-8")
    return path


@pytest.fixture(name="write_lock")
def fixture_write_lock(db_path: Path) -> Iterator[Callable[[str], None]]:
    """Factory: hold a write or read transaction from a second connection."""
    conns: list[sqlite3.Connection] = []

    def hold(kind: str) -> None:
        conn = sqlite3.connect(db_path, autocommit=True)
        conns.append(conn)
        conn.execute("BEGIN IMMEDIATE" if kind == "write" else "BEGIN")
        conn.execute("SELECT count(*) FROM project").fetchone()

    yield hold
    for conn in conns:
        conn.close()


@pytest.fixture(name="marker")
def fixture_marker() -> str:
    """The text planted in secret_item, to search output and disk for."""
    return MARKER


@pytest.fixture(name="disk_hits")
def fixture_disk_hits(db_path: Path) -> Callable[[str], int]:
    """Factory: count a marker in the raw bytes of the database and its WAL."""

    def hits(needle: str) -> int:
        files = [db_path, db_path.with_name(db_path.name + "-wal")]
        return sum(p.read_bytes().count(needle.encode()) for p in files if p.exists())

    return hits
