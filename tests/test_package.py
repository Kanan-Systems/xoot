"""Smoke test: the package imports and exposes a version string."""

import xoot


def test_version_is_string() -> None:
    """The package exposes ``__version__`` as a string."""
    assert isinstance(xoot.__version__, str)
