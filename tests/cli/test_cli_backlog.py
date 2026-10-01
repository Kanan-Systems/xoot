"""
`xoot backlog`: the open backlog, grouped as backlog_list orders it, with
--at, --all and --json; read-only; the usual exit codes.
"""

from collections.abc import Callable
from typing import Any

from xoot.cli import exit_codes
from xoot.models.item.item import Item
from xoot.models.project.project import Project


def _backlog(
    capture_on: Callable[..., Item], set_state: Callable[..., Item], tree: Any
) -> tuple[Item, Item, Item]:
    """On the batch (via a subtask), on the goal, and a done one on the goal."""
    goal, _, first, _ = tree
    on_batch = capture_on(first, "batch work")
    on_goal = capture_on(goal, "goal work")
    closed = set_state(capture_on(goal, "closed work"), "done")
    return on_batch, on_goal, closed


def test_text_groups_by_holder(
    xoot: Any,
    work_tree: Any,
    capture_on: Callable[..., Item],
    set_state: Callable[..., Item],
) -> None:
    """A heading per holder, open items only."""
    _backlog(capture_on, set_state, work_tree)
    run = xoot("backlog", "--project", "xoot")
    assert run.code == 0, run.err
    assert run.out == (
        "on goal-1 (goal backlog)\n"
        "  goal-1/backlog-1  open (open)  goal work  (found on goal-1)\n"
        "on goal-1/batch-1 (batch backlog)\n"
        "  goal-1/batch-1/backlog-1  open (open)  batch work"
        "  (found on goal-1/batch-1/subtask-1)\n"
    )


def test_json_all_and_at(
    xoot: Any,
    work_tree: Any,
    capture_on: Callable[..., Item],
    set_state: Callable[..., Item],
) -> None:
    """--json has backlog_list's shape; --all adds closed; --at narrows."""
    _backlog(capture_on, set_state, work_tree)
    every = xoot("backlog", "--project", "xoot", "--all", "--json").json()
    assert set(every) == {"project", "resolved_by", "at", "items", "truncated"}
    assert [item["key"] for item in every["items"]] == [
        "goal-1/backlog-1",
        "goal-1/backlog-2",
        "goal-1/batch-1/backlog-1",
    ]
    assert every["items"][1]["category"] == "done"
    narrowed = xoot("backlog", "--at", "xoot:goal-1/batch-1", "--json").json()
    assert narrowed["at"] == "goal-1/batch-1"
    assert narrowed["resolved_by"] == "qualified"
    assert [item["level"] for item in narrowed["items"]] == ["batch"]


def test_empty_and_errors(xoot: Any, project: Project, row_counts: Any) -> None:
    """Nothing to show; an unknown key or project is a refusal; nothing is written."""
    assert project.key_prefix == "xoot"
    before = row_counts()
    assert xoot("backlog", "--project", "xoot").out == "(no backlog)\n"
    missing = xoot("backlog", "--project", "xoot", "--at", "goal-9")
    assert missing.code == exit_codes.ERROR
    assert missing.err.startswith("error: NotFoundError:")
    unknown = xoot("backlog", "--project", "nope")
    assert unknown.code == exit_codes.ERROR
    assert unknown.err.startswith("error: ProjectResolutionError:")
    assert row_counts() == before


def test_rename_takes_the_project_either_way(
    xoot: Any, project: Project, db_path: Any
) -> None:
    """--project works like PROJECT; both or neither is a usage error."""
    assert project.key_prefix == "xoot"
    by_option = xoot("project", "rename", "--project", "xo", "--name", "A", "--yes")
    assert by_option.code == 0, by_option.err
    same = xoot(
        "project", "rename", "xoot", "--project", "xoot", "--name", "B", "--yes"
    )
    assert same.code == 0, same.err
    for argv in (
        ["xoot", "--project", "xo", "--name", "C"],
        ["--name", "C"],
    ):
        run = xoot("project", "rename", *argv, "--yes")
        assert run.code == exit_codes.USAGE
        assert "name the project once: PROJECT or --project" in run.err
        assert "usage: xoot project rename" in run.err
    assert db_path.exists()
