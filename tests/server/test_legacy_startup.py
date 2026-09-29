"""
xoot-mcp on a 0.2 database: one startup WARNING on stderr naming the path
and the fix, while every tool call still fails with LegacyDatabaseError and
the file stays byte-identical.
"""

import hashlib
import logging
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession

from xoot.server.__main__ import warn_if_legacy
from xoot.store.paths import prepare_db_file
from xoot.store.store import Store


def _legacy_file(db_path: Path) -> Path:
    """A 0.2-shaped file: a session table and schema version 1."""
    prepare_db_file(db_path)
    raw = sqlite3.connect(db_path)
    raw.execute("CREATE TABLE session (id INTEGER PRIMARY KEY, title TEXT) STRICT")
    raw.execute("PRAGMA user_version = 1")
    raw.commit()
    raw.close()
    return db_path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_startup_warns_once_and_calls_still_fail(
    db_path: Path, harness: Any, server_stderr: Path
) -> None:
    """The warning names the path and the fix; the per-call error is kept."""
    _legacy_file(db_path)
    before = _digest(db_path)

    async def scenario(client: ClientSession) -> list[str]:
        return [
            await harness.error(client, "projects_list"),
            await harness.error(client, "tree_get", project="xoot"),
        ]

    messages = harness.run(scenario)
    assert all("LegacyDatabaseError" in message for message in messages)
    log = server_stderr.read_text(encoding="utf-8")
    warnings = [line for line in log.splitlines() if "WARNING" in line]
    assert len(warnings) == 1
    assert str(db_path) in warnings[0]
    assert "xoot 0.2" in warnings[0]
    assert "Move the file aside" in warnings[0]
    assert "xoot init" in warnings[0]
    assert _digest(db_path) == before


def test_no_warning_for_a_current_or_missing_database(
    db_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A missing file is not created, and a current database is quiet."""
    caplog.set_level(logging.WARNING, logger="xoot.server")
    warn_if_legacy(db_path)
    assert not db_path.exists()
    Store.open(db_path).close()
    warn_if_legacy(db_path)
    assert caplog.records == []


def test_symlink_is_not_followed(
    tmp_path: Path, db_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A symlinked path is left to the store's own refusal."""
    caplog.set_level(logging.WARNING, logger="xoot.server")
    target = _legacy_file(db_path)
    link = tmp_path / "link.db"
    link.symlink_to(target)
    warn_if_legacy(link)
    assert caplog.records == []
