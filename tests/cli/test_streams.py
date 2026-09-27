"""
T8: results go to stdout, errors and warnings to stderr. An error leaves
stdout empty; a success leaves stderr empty unless it warns.
"""

from typing import Any

import pytest

from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project


@pytest.mark.usefixtures("project")
@pytest.mark.parametrize("json_mode", [[], ["--json"]], ids=["text", "json"])
@pytest.mark.parametrize(
    "argv",
    [
        ["brief", "--project", "zz"],
        ["tree", "--project", "xo", "--root", "xoot-99"],
        ["project", "add-alias", "xo", "--project", "xoot"],
        ["redact", "xoot-99", "title", "--yes"],
        ["workflow", "import", "/nonexistent.toml", "--project", "xo", "--yes"],
    ],
)
def test_errors_leave_stdout_empty(
    xoot: Any, argv: list[str], json_mode: list[str]
) -> None:
    """One "error: " line on stderr and nothing on stdout, in either mode."""
    run = xoot(*argv, *json_mode)
    assert run.code == 1 and run.out == ""
    assert run.err.startswith("error: ") and run.err.count("\n") == 1


@pytest.mark.usefixtures("project")
@pytest.mark.parametrize(
    "argv",
    [["project", "list"], ["brief", "--project", "xo"], ["db", "stats", "--json"]],
)
def test_success_leaves_stderr_empty(xoot: Any, argv: list[str]) -> None:
    """No log line or notice on stderr when nothing needs warning about."""
    run = xoot(*argv)
    assert run.code == 0 and run.out and run.err == ""


def test_warnings_go_to_stderr(xoot: Any, project: Project, make_item: Any) -> None:
    """A truncated tree prints its warning on stderr; stdout stays pure JSON."""
    goal: Item = make_item(project, ItemKind.GOAL)
    make_item(project, ItemKind.BATCH, parent_id=goal.id)
    run = xoot("tree", "--project", "xo", "--depth", "0", "--json")
    assert run.code == 0
    assert [n["item"]["key"] for n in run.json()["nodes"]] == ["xoot-1"]
    assert run.err == "warning: the tree was truncated by --depth or the item limit\n"


def test_stored_text_cannot_control_the_terminal(
    xoot: Any, project: Project, make_item: Any
) -> None:
    """Escape sequences and bidi overrides in titles are shown escaped."""
    make_item(project, ItemKind.GOAL, title="evil\x1b[2J\u202etitle", state="active")
    for argv in (["tree", "--project", "xo"], ["brief", "--project", "xo"]):
        out = xoot(*argv).out
        assert "\x1b" not in out and "\u202e" not in out
        assert "evil\\u001b[2J\\u202etitle" in out
