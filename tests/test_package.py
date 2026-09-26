"""The package exposes the version declared in pyproject.toml."""

import tomllib
from importlib.metadata import version
from pathlib import Path

import xoot

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_version_is_string() -> None:
    """The package exposes ``__version__`` as a string."""
    assert isinstance(xoot.__version__, str)


def test_version_comes_from_metadata() -> None:
    """__version__ is the installed metadata, which mirrors pyproject.toml."""
    declared = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"][
        "version"
    ]
    assert xoot.__version__ == version("xoot") == declared
