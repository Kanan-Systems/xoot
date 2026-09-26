"""Store lifecycle: opening with explicit or default paths, and closing."""

import sqlite3
import stat
from pathlib import Path

import pytest

from xoot.models.event.actor import Actor
from xoot.models.project.project_registration import ProjectRegistration
from xoot.services.project_service import register_project
from xoot.store.store import Store


def test_open_explicit_path(db_path: Path) -> None:
    """The store opens exactly the path it is given, with owner-only modes."""
    with Store.open(db_path) as store:
        assert store.path == db_path
        assert stat.S_IMODE(db_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(db_path.parent.stat().st_mode) == 0o700


def test_open_default_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Without a path the XDG location is used (redirected into tmp_path)."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    with Store.open() as store:
        assert store.path == tmp_path / "xoot" / "xoot.db"
        assert store.path.exists()


def test_context_manager_closes(db_path: Path) -> None:
    """Leaving the with-block closes the connection."""
    with Store.open(db_path) as store:
        conn = store.conn
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


@pytest.mark.usefixtures("open_umask")
def test_wal_and_shm_files_are_owner_only(db_path: Path, user: Actor) -> None:
    """SQLite's sidecar files hold the same data and inherit the 0600 mode."""
    with Store.open(db_path) as store:
        register_project(store, ProjectRegistration(key_prefix="xo", name="x"), user)
        for suffix in ("-wal", "-shm"):
            sidecar = db_path.with_name(db_path.name + suffix)
            assert stat.S_IMODE(sidecar.stat().st_mode) == 0o600
