"""Project registration input validation."""

import pytest
from pydantic import ValidationError

from xoot.models.project.project_registration import ProjectRegistration


def test_paths_are_normalized() -> None:
    """Registered paths are stored in normalized form."""
    registration = ProjectRegistration(key_prefix="xo", name="x", paths=("/a/b/",))
    assert registration.paths == ("/a/b",)


def test_duplicate_aliases_are_rejected() -> None:
    """The same alias twice is an input error."""
    with pytest.raises(ValidationError, match="aliases must be unique"):
        ProjectRegistration(key_prefix="xo", name="x", aliases=("ab", "ab"))


def test_paths_equal_after_normalization_are_rejected() -> None:
    """Two spellings of one directory count as a duplicate."""
    with pytest.raises(ValidationError, match="paths must be unique"):
        ProjectRegistration(key_prefix="xo", name="x", paths=("/a/b", "/a//b/"))
