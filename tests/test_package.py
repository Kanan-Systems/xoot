"""The package exposes its version and ships its typing marker."""

import tomllib
from importlib import resources
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


def test_typing_marker_is_shipped() -> None:
    """PEP 561: py.typed marks xoot's annotations as usable by type checkers."""
    marker = resources.files("xoot").joinpath("py.typed")
    assert marker.is_file()
    assert marker.read_bytes() == b""
