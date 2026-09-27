"""Path resolution by longest whole-segment match; alias by exact match."""

import pytest
from pydantic import ValidationError

from xoot.models.event.write_context import WriteContext
from xoot.models.project.project import Project
from xoot.services.project_resolver import ancestors, resolve_by_alias, resolve_by_path
from xoot.services.project_service import add_path
from xoot.store.store import Store


@pytest.fixture(name="nested")
def fixture_nested(
    store: Store, project: Project, other_project: Project, ctx: WriteContext
) -> tuple[Project, Project]:
    """xoot owns /work/xoot; nova owns the nested /work/xoot/vendor/nova."""
    add_path(store, other_project.id, "/work/xoot/vendor/nova", ctx)
    return project, other_project


def _key(store: Store, path: str) -> str | None:
    found = resolve_by_path(store, path)
    return None if found is None else found.key_prefix


@pytest.mark.usefixtures("nested")
@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/work/xoot", "xoot"),
        ("/work/xoot/", "xoot"),
        ("/work/xoot/src/deep/dir", "xoot"),
        ("/work/xoot/vendor", "xoot"),
        ("/work/xoot/vendor/nova", "nova"),
        ("/work/xoot/vendor/nova/lib", "nova"),
        ("/work/xoot/vendor/./nova/../nova/lib", "nova"),
    ],
)
def test_longest_segment_match_wins(store: Store, path: str, expected: str) -> None:
    """The deepest registered ancestor (or the path itself) decides."""
    assert _key(store, path) == expected


@pytest.mark.usefixtures("nested")
@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/work/xoot2", None),
        ("/work/xoot2/src", None),
        ("/work/xoo", None),
        ("/work/xoot/vendor/nova2", "xoot"),
    ],
)
def test_segment_boundary(store: Store, path: str, expected: str | None) -> None:
    """A registered path never matches a sibling that merely shares a prefix."""
    assert _key(store, path) == expected


@pytest.mark.usefixtures("project")
def test_unknown_path(store: Store) -> None:
    """A path under no registered directory resolves to nothing."""
    assert resolve_by_path(store, "/elsewhere/entirely") is None
    assert resolve_by_path(store, "/") is None


@pytest.mark.usefixtures("project")
def test_relative_path_is_rejected(store: Store) -> None:
    """Resolution only accepts absolute paths."""
    with pytest.raises(ValidationError):
        resolve_by_path(store, "work/xoot")


def test_alias_is_exact(store: Store, project: Project) -> None:
    """Aliases match exactly, never by prefix."""
    found = resolve_by_alias(store, "xo")
    assert found is not None and found.id == project.id
    assert resolve_by_alias(store, "xoo") is None
    with pytest.raises(ValidationError):
        resolve_by_alias(store, "x")


def test_ancestors_are_whole_segments() -> None:
    """Candidates are the path and each parent directory, longest first."""
    assert ancestors("/a/xoot/src") == ["/a/xoot/src", "/a/xoot", "/a", "/"]
    assert ancestors("/") == ["/"]
