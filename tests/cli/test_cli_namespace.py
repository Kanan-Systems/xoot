"""
T4: namespace refusals in both directions, "/" refused, and project
resolution by prefix, alias and working directory through the CLI.
"""

from pathlib import Path
from typing import Any

import pytest

from xoot.models.project.project import Project


@pytest.mark.usefixtures("project", "other_project")
@pytest.mark.parametrize(
    "argv",
    [
        ["init", "/work/a", "--prefix", "xo"],
        ["init", "/work/a", "--prefix", "newp", "--alias", "nova"],
        ["project", "add-alias", "xoot", "--project", "nova"],
        ["project", "add-alias", "xo", "--project", "nova"],
    ],
    ids=["prefix=alias", "alias=prefix", "add prefix", "add alias"],
)
def test_names_of_another_project_are_refused(
    xoot: Any, row_counts: Any, argv: list[str]
) -> None:
    """Each cross-project clash exits 1 and writes nothing."""
    before = row_counts()
    run = xoot(*argv)
    assert run.code == 1 and run.err.startswith("error: DuplicateError: ")
    assert row_counts() == before


@pytest.mark.usefixtures("project")
def test_own_prefix_alias_is_accepted(xoot: Any) -> None:
    """An alias equal to the project's own prefix registers and resolves."""
    assert xoot("init", "/work/self", "--prefix", "selfp", "--alias", "selfp").code == 0
    assert xoot("project", "add-alias", "xoot", "--project", "xo").code == 0
    shown = xoot("project", "show", "--project", "selfp", "--json").json()
    assert shown["aliases"] == ["selfp"]


@pytest.mark.parametrize(
    "argv",
    [
        ["init", "/", "--prefix", "rootp"],
        ["init", "/..", "--prefix", "rootp"],
        ["project", "add-path", "/", "--project", "xo"],
    ],
)
@pytest.mark.usefixtures("project")
def test_root_is_refused(xoot: Any, row_counts: Any, argv: list[str]) -> None:
    """ "/" is never a project path, however it is spelled; the error names path."""
    before = row_counts()
    run = xoot(*argv)
    assert run.code == 1 and run.err == (
        "error: ValidationError: path: Value error, "
        "a project directory cannot be the root directory\n"
    )
    assert row_counts() == before


@pytest.mark.usefixtures("project", "other_project")
@pytest.mark.parametrize(
    ("name", "prefix", "resolved_by"),
    [("xoot", "xoot", "prefix"), ("xo", "xoot", "alias"), ("nova", "nova", "prefix")],
)
def test_resolution_by_prefix_or_alias(
    xoot: Any, name: str, prefix: str, resolved_by: str
) -> None:
    """--project takes a prefix (even with no alias) or an alias, and says which."""
    brief = xoot("brief", "--project", name, "--json").json()
    assert (brief["project"]["key_prefix"], brief["resolved_by"]) == (
        prefix,
        resolved_by,
    )


def test_resolution_by_working_directory(
    xoot: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without --project the longest whole-segment path match wins."""
    outer, inner = tmp_path / "work", tmp_path / "work" / "inner"
    (inner / "deep").mkdir(parents=True)
    (tmp_path / "work2").mkdir()
    assert xoot("init", str(outer), "--prefix", "outer").code == 0
    assert xoot("init", str(inner), "--prefix", "inner").code == 0
    for cwd, expected in (
        (inner / "deep", "inner"),
        (outer, "outer"),
    ):
        monkeypatch.chdir(cwd)
        tree = xoot("tree", "--json").json()
        assert (tree["project"], tree["resolved_by"]) == (expected, "cwd")
    monkeypatch.chdir(tmp_path / "work2")
    run = xoot("tree")
    assert run.code == 1 and "one of: inner, outer" in run.err


def test_remove_then_resolve(xoot: Any, project: Project) -> None:
    """A removed alias no longer resolves; the prefix still does."""
    assert xoot("project", "remove-alias", "xo", "--project", "xo", "--yes").code == 0
    assert xoot("brief", "--project", "xo").code == 1
    assert xoot("brief", "--project", project.key_prefix).code == 0
