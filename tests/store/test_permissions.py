"""
X7: every open lstat-s the data directory, the database and any WAL/SHM file,
and refuses a symlink, a foreign owner or a group/other permission bit.
"""

import os
import stat
from pathlib import Path

import pytest

from xoot.exceptions.unsafe_path_error import UnsafePathError
from xoot.store.store import Store

TARGETS = ("dir", "db", "-wal", "-shm")
LOOSE_MODES = {"group": (0o750, 0o640), "other": (0o705, 0o604)}


def _target(db_path: Path, target: str) -> Path:
    if target == "dir":
        return db_path.parent
    if target == "db":
        return db_path
    return db_path.with_name(db_path.name + target)


def _private_file(path: Path) -> None:
    os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))


def _existing_store(db_path: Path, target: str) -> Path:
    """A closed store whose target path exists and is private."""
    Store.open(db_path).close()
    path = _target(db_path, target)
    if target.startswith("-"):
        _private_file(path)
    return path


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


def _refused(db_path: Path, path: Path) -> UnsafePathError:
    with pytest.raises(UnsafePathError) as caught:
        Store.open(db_path)
    message = str(caught.value)
    assert caught.value.path == path
    assert str(path) in message
    assert f"mode {caught.value.mode:04o}" in message
    return caught.value


@pytest.mark.parametrize("target", TARGETS)
def test_symlink_is_refused(tmp_path: Path, db_path: Path, target: str) -> None:
    """A symlink anywhere in the set is refused, even to a private target."""
    elsewhere = tmp_path / "elsewhere"
    if target == "dir":
        elsewhere.mkdir(mode=0o700)
        db_path.parent.symlink_to(elsewhere)
        path = db_path.parent
    else:
        path = _existing_store(db_path, target)
        path.rename(elsewhere)
        path.symlink_to(elsewhere)
    error = _refused(db_path, path)
    assert "symlink" in str(error)
    if target == "dir":
        # Refused before anything was created through the link.
        assert not any(elsewhere.iterdir())


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("who", list(LOOSE_MODES))
def test_group_or_other_bit_is_refused(db_path: Path, target: str, who: str) -> None:
    """Any group or other bit fails the open, and the mode is left as found."""
    path = _existing_store(db_path, target)
    loose = LOOSE_MODES[who][0 if target == "dir" else 1]
    path.chmod(loose)
    error = _refused(db_path, path)
    assert error.mode == loose
    assert _mode(path) == loose


@pytest.mark.parametrize("target", TARGETS)
def test_foreign_owner_is_refused(
    monkeypatch: pytest.MonkeyPatch, db_path: Path, target: str
) -> None:
    """A path owned by another uid is refused (lstat reports a foreign owner)."""
    path = _existing_store(db_path, target)
    real_lstat = os.lstat

    def foreign_lstat(candidate: os.PathLike[str] | str) -> os.stat_result:
        info = real_lstat(candidate)
        if Path(candidate) != path:
            return info
        fields = list(info[:10])
        fields[stat.ST_UID] = os.getuid() + 1
        return os.stat_result(fields)

    monkeypatch.setattr(os, "lstat", foreign_lstat)
    error = _refused(db_path, path)
    assert f"owned by uid {os.getuid() + 1}" in str(error)


def test_private_sidecars_of_an_open_store_are_accepted(db_path: Path) -> None:
    """A second open sees the first one's 0600 WAL/SHM files and proceeds."""
    with Store.open(db_path):
        assert _target(db_path, "-wal").exists()
        with Store.open(db_path) as second:
            assert second.path == db_path
