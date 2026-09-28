"""`xoot --version` prints the package version and opens no database."""

from importlib.metadata import version
from pathlib import Path
from typing import Any


def test_version_prints_package_version(xoot: Any, db_path: Path) -> None:
    """stdout gets "xoot <version>", the exit code is 0, nothing is opened."""
    run = xoot("--version")
    assert run.code == 0
    assert run.out == f"xoot {version('xoot')}\n"
    assert run.err == ""
    assert not db_path.exists()
