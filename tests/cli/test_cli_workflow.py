"""
Workflow export and import through the CLI; the model-level round trips
are in tests/services/test_workflow_toml.py.
"""

import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.services.item_service import get_item
from xoot.services.workflow_service import get_active_workflow
from xoot.services.workflow_toml import MAX_BYTES, dump_workflow
from xoot.store.store import Store


@pytest.fixture(name="renamed_toml")
def fixture_renamed_toml(tmp_path: Path) -> Path:
    """The default workflow with the goal state "blocked" renamed to "stuck"."""
    text = dump_workflow(WorkflowDefinition.default())
    goal, rest = text.split("[kinds.batch]", 1)
    goal = goal.replace('name = "blocked"', 'name = "stuck"')
    path = tmp_path / "renamed.toml"
    path.write_text(goal + "[kinds.batch]" + rest, encoding="utf-8")
    return path


@pytest.fixture(name="blocked_goal")
def fixture_blocked_goal(project: Project, make_item: Callable[..., Item]) -> Item:
    """A goal in the state the renamed workflow removes."""
    return make_item(project, ItemKind.GOAL, state="blocked")


def test_export_round_trips_through_the_cli(
    xoot: Any, tmp_path: Path, store: Store, project: Project, row_counts: Any
) -> None:
    """Export -> import of the same file is a no-op: no version, no events."""
    target = tmp_path / "wf.toml"
    assert xoot("workflow", "export", "--project", "xo", "-o", str(target)).code == 0
    definition = WorkflowDefinition.model_validate(tomllib.loads(target.read_text()))
    assert definition == get_active_workflow(store, project.id).definition
    before = row_counts()
    run = xoot("workflow", "import", str(target), "--project", "xo", "--yes", "--json")
    assert (run.json()["version"], run.json()["changed"]) == (1, False)
    assert get_active_workflow(store, project.id).definition == definition
    assert row_counts() == before


@pytest.mark.usefixtures("project")
def test_identical_import_prints_no_changes_without_asking(
    xoot: Any, default_toml: Path, row_counts: Any
) -> None:
    """No prompt is needed for a no-op, so no terminal or --yes is either."""
    before = row_counts()
    run = xoot("workflow", "import", str(default_toml), "--project", "xo")
    assert (run.code, run.err) == (0, "")
    assert run.out == "no changes: xoot workflow is still version 1\n"
    assert row_counts() == before


@pytest.mark.usefixtures("project")
def test_changed_import_reports_the_new_version(xoot: Any, changed_toml: Path) -> None:
    """A real change still adds a version and says so."""
    run = xoot("workflow", "import", str(changed_toml), "--project", "xo", "--yes")
    assert run.code == 0, run.err
    assert run.out.startswith("xoot workflow is now version 2\n")


def test_import_with_a_mapping_applies(
    xoot: Any, store: Store, renamed_toml: Path, blocked_goal: Item
) -> None:
    """The mapped item moves to the new state; the output counts it."""
    run = xoot(
        "workflow", "import", str(renamed_toml), "--project", "xo",
        "--map", "goal:blocked=stuck", "--yes", "--json",
    )  # fmt: skip
    assert run.code == 0, run.err
    assert run.json()["plan"] == {
        "removed": {"goal": ["blocked"], "batch": [], "subtask": [], "backlog": []},
        "remaps": {"goal": 1, "batch": 0, "subtask": 0, "backlog": 0},
    }
    assert get_item(store, blocked_goal.id).state == "stuck"


@pytest.mark.usefixtures("blocked_goal")
@pytest.mark.parametrize(
    "extra",
    [[], ["--map", "goal:open=stuck"], ["--map", "goal:blocked=gone"]],
    ids=["no mapping", "maps a kept state", "unknown target"],
)
def test_import_without_a_valid_mapping_writes_nothing(
    xoot: Any, row_counts: Any, renamed_toml: Path, extra: list[str]
) -> None:
    """A stranded item is refused before any prompt: exit 1, no row written."""
    before = row_counts()
    run = xoot(
        "workflow", "import", str(renamed_toml), "--project", "xo", "--yes", *extra
    )
    assert run.code == 1 and run.out == ""
    assert row_counts() == before


@pytest.mark.usefixtures("project")
def test_oversized_file_is_refused(xoot: Any, tmp_path: Path, row_counts: Any) -> None:
    """A file over 64 KiB is refused without being parsed."""
    big = tmp_path / "big.toml"
    big.write_text("#" * (MAX_BYTES + 1), encoding="utf-8")
    before = row_counts()
    run = xoot("workflow", "import", str(big), "--project", "xo", "--yes")
    assert run.code == 1
    assert run.err == (
        "error: WorkflowFileError: the workflow file is larger than 65536 bytes\n"
    )
    assert row_counts() == before


@pytest.mark.usefixtures("project")
def test_invalid_definition_names_the_location(xoot: Any, tmp_path: Path) -> None:
    """Errors name where the file is wrong, cleaned, and never quote a value."""
    bad = tmp_path / "bad.toml"
    bad.write_text('[kinds.goal]\n"k\\u001b[2J" = "hidden-value"\n', encoding="utf-8")
    run = xoot("workflow", "import", str(bad), "--project", "xo", "--yes")
    assert run.code == 1
    assert run.err.startswith("error: ValidationError: ")
    assert "kinds.goal.k\\u001b[2J: Extra inputs are not permitted" in run.err
    assert "hidden-value" not in run.err and "\x1b" not in run.err
