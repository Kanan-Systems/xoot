"""
Exit codes 1, 2 and 3, each triggered for real, and the error line
format "error: <Class>: <reason>" with no SQL or driver text.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from xoot.cli.__main__ import main
from xoot.models.item.item import Item
from xoot.models.project.project import Project

SQL_WORDS = ("SELECT", "INSERT", "UPDATE", "CREATE", "sqlite3", "Traceback")


def _run_on(
    db: Path, capsys: pytest.CaptureFixture[str], *argv: str
) -> tuple[int, str, str]:
    code = main(["--db", str(db), *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.usefixtures("project")
def test_refused_request_exits_1(xoot: Any) -> None:
    """An unresolved project is an XootError: exit 1, a fixed line."""
    run = xoot("project", "show", "--project", "nope")
    assert run.code == 1
    assert (
        run.err
        == "error: ProjectResolutionError: project not resolved; one of: xo, xoot\n"
    )


def test_usage_exits_2(xoot: Any) -> None:
    """An unknown command is argparse's usage error."""
    assert xoot("frobnicate").code == 2


def test_unsafe_path_exits_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A group-writable data directory is refused, never chmod-ed."""
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o775)
    shared.chmod(0o775)
    code, out, err = _run_on(shared / "x.db", capsys, "db", "stats")
    assert (code, out) == (3, "")
    assert err.startswith("error: UnsafePathError: refusing to open")
    assert oct(shared.stat().st_mode & 0o777) == "0o775"


def test_store_open_failure_exits_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A private file that is not a database cannot be opened."""
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    garbage = private / "x.db"
    garbage.write_bytes(b"not a database" * 100)
    garbage.chmod(0o600)
    code, out, err = _run_on(garbage, capsys, "project", "list")
    assert (code, out) == (3, "")
    assert err.startswith("error: StoreOpenError: could not open the database")
    assert not any(word in err for word in SQL_WORDS)


@pytest.mark.usefixtures("project")
def test_busy_database_exits_3(xoot: Any, write_lock: Callable[[str], None]) -> None:
    """Another connection's write lock keeps vacuum from running."""
    write_lock("write")
    run = xoot("db", "vacuum")
    assert (run.code, run.out) == (3, "")
    assert run.err == (
        "error: DatabaseBusyError: database busy: close clients and retry\n"
    )


def test_incomplete_purge_exits_3(
    xoot: Any, secret_item: Item, write_lock: Callable[[str], None]
) -> None:
    """A reader pinning the WAL leaves the redaction committed but unpurged."""
    write_lock("read")
    run = xoot("redact", f"xoot:{secret_item.key}", "title", "--yes", "--json")
    assert run.code == 3
    assert run.json()["purged"] is False
    assert run.err.startswith("warning: the redaction is committed")
    assert "redo the redaction" in run.err


def test_help_is_not_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    """main returns 0 after --help instead of raising SystemExit."""
    assert main(["--help"]) == 0
    assert capsys.readouterr().out.startswith("usage: xoot")


def test_duplicate_is_reported_by_value(xoot: Any, project: Project) -> None:
    """A refused duplicate names the value and its holder, nothing from SQLite."""
    run = xoot("init", "/work/other", "--prefix", project.key_prefix)
    assert run.code == 1
    assert run.err == (
        "error: DuplicateError: 'xoot' is already registered as the prefix of "
        "project xoot\n"
    )
