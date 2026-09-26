"""Default DB path resolution and owner-only file creation."""

import stat
from pathlib import Path

import pytest

from xoot.store.paths import default_db_path, prepare_db_file


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_default_uses_absolute_xdg_data_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An absolute XDG_DATA_HOME is used as the base."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert default_db_path() == tmp_path / "xoot" / "xoot.db"


@pytest.mark.parametrize("value", [None, "", "relative/dir"])
def test_default_falls_back_to_local_share(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str | None
) -> None:
    """Unset, empty or relative XDG_DATA_HOME falls back to ~/.local/share."""
    monkeypatch.setenv("HOME", str(tmp_path))
    if value is None:
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    else:
        monkeypatch.setenv("XDG_DATA_HOME", value)
    assert default_db_path() == tmp_path / ".local" / "share" / "xoot" / "xoot.db"


@pytest.mark.usefixtures("open_umask")
def test_creates_directory_0700_and_file_0600(tmp_path: Path) -> None:
    """New directory and file get owner-only modes regardless of umask."""
    path = tmp_path / "new" / "xoot.db"
    prepare_db_file(path)
    assert _mode(path.parent) == 0o700
    assert _mode(path) == 0o600


@pytest.mark.usefixtures("open_umask")
def test_existing_directory_mode_is_left_alone(tmp_path: Path) -> None:
    """A directory the caller already has is never chmod-ed."""
    directory = tmp_path / "shared"
    directory.mkdir(mode=0o755)
    prepare_db_file(directory / "xoot.db")
    assert _mode(directory) == 0o755
    assert _mode(directory / "xoot.db") == 0o600


def test_existing_file_is_kept(tmp_path: Path) -> None:
    """Preparing twice neither fails nor truncates the file."""
    path = tmp_path / "xoot.db"
    prepare_db_file(path)
    path.write_bytes(b"data")
    prepare_db_file(path)
    assert path.read_bytes() == b"data"
