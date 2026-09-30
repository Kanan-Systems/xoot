"""
`project rename` changes only the display name and adds an alias, records
the old and new name in an update event, and a redaction of the name
scrubs both from that event and from disk.
"""

from collections.abc import Callable
from typing import Any

import pytest

from xoot.models.event.entity_type import EntityType
from xoot.models.project.project import Project
from xoot.repositories.event import event_db
from xoot.services.project_service import get_project
from xoot.services.redaction_service import REDACTED
from xoot.store.store import Store


def _project_events(store: Store, project: Project) -> list[tuple[str, Any, Any]]:
    with store.read() as conn:
        events = event_db.list_for_entity(conn, EntityType.PROJECT, project.id)
    return [(e.action, e.before, e.after) for e in events]


def test_rename_changes_the_name_and_adds_an_alias(
    xoot: Any, store: Store, project: Project
) -> None:
    """The prefix stays; the name and the new alias show in the result."""
    run = xoot(
        "project",
        "rename",
        "xoot",
        "--name",
        "Kanan Root",
        "--alias",
        "kroot",
        "--yes",
        "--json",
    )
    assert run.code == 0, run.err
    shown = run.json()
    assert (shown["key_prefix"], shown["name"]) == ("xoot", "Kanan Root")
    assert shown["aliases"] == ["kroot", "xo"]
    renamed = get_project(store, project.id)
    assert (renamed.key_prefix, renamed.name) == ("xoot", "Kanan Root")
    assert _project_events(store, project)[-2:] == [
        ("update", {"name": "xoot"}, {"name": "Kanan Root"}),
        ("add_alias", None, {"alias": "kroot"}),
    ]


def test_rename_resolves_the_project_by_alias(
    xoot: Any, store: Store, project: Project
) -> None:
    """PROJECT may be an alias; --alias alone leaves the name as it was."""
    run = xoot("project", "rename", "xo", "--alias", "xroot", "--yes")
    assert run.code == 0, run.err
    assert get_project(store, project.id).name == "xoot"
    assert _project_events(store, project)[-1] == (
        "add_alias",
        None,
        {"alias": "xroot"},
    )


@pytest.mark.usefixtures("project")
def test_the_prompt_shows_the_old_and_new_name(xoot: Any) -> None:
    """The confirmation lists both names and the alias before asking."""
    run = xoot(
        "project", "rename", "xoot", "--name", "New", "--alias", "nw", answer="y"
    )
    assert run.code == 0, run.err
    assert run.err == (
        "rename project xoot: 'xoot' -> 'New'\n"
        "add alias nw to project xoot\n"
        "Proceed? [y/N] "
    )


def test_a_refused_prompt_writes_nothing(
    xoot: Any, store: Store, project: Project, row_counts: Any
) -> None:
    """No answers no; no terminal and no --yes refuses; both exit 1."""
    before = row_counts()
    assert xoot("project", "rename", "xoot", "--name", "New", answer="n").code == 1
    run = xoot("project", "rename", "xoot", "--name", "New")
    assert run.code == 1
    assert "pass --yes" in run.err
    assert row_counts() == before
    assert get_project(store, project.id).name == "xoot"


@pytest.mark.usefixtures("project")
def test_neither_name_nor_alias_is_a_usage_error(xoot: Any, row_counts: Any) -> None:
    """Exit 2 and nothing written."""
    before = row_counts()
    run = xoot("project", "rename", "xoot", "--yes")
    assert (run.code, run.out) == (2, "")
    assert run.err == "error: pass --name, --alias or both\n"
    assert row_counts() == before


@pytest.mark.usefixtures("project")
@pytest.mark.parametrize(
    ("argv", "error"),
    [
        (["xoot", "--name", ""], "error: ValidationError: name: "),
        (["xoot", "--alias", "goal-1"], "error: ValidationError: alias: "),
        (["xoot", "--alias", "xo"], "error: DuplicateError: "),
        (["nope", "--name", "N"], "error: ProjectResolutionError: "),
    ],
)
def test_refusals_exit_1_and_write_nothing(
    xoot: Any, row_counts: Any, argv: list[str], error: str
) -> None:
    """Bad input, a taken alias and an unknown project are refused."""
    before = row_counts()
    run = xoot("project", "rename", *argv, "--yes")
    assert (run.code, run.out) == (1, "")
    assert run.err.startswith(error), run.err
    assert row_counts() == before


def test_redaction_scrubs_both_names_from_the_rename_event(
    xoot: Any, store: Store, project: Project, disk_hits: Callable[[str], int]
) -> None:
    """Old and new name leave the update event and the database files."""
    old, new = "old-name-secret-3e9a", "new-name-secret-8b1d"
    assert xoot("project", "rename", "xoot", "--name", old, "--yes").code == 0
    assert xoot("project", "rename", "xoot", "--name", new, "--yes").code == 0
    assert disk_hits(old) > 0 and disk_hits(new) > 0
    run = xoot("redact", "xoot", "name", "--yes")
    assert run.code == 0, run.err
    updates = [e for e in _project_events(store, project) if e[0] == "update"]
    assert updates == [
        ("update", {"name": REDACTED}, {"name": REDACTED}),
        ("update", {"name": REDACTED}, {"name": REDACTED}),
    ]
    assert get_project(store, project.id).name == REDACTED
    assert disk_hits(old) == 0 and disk_hits(new) == 0
