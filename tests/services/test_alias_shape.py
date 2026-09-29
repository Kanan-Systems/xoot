"""
Aliases may hold dashes but must not look like an item or decision key
segment, in the model, the service and SQL; re-adding a project's own alias
says so rather than naming the project as a stranger.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from xoot.exceptions.duplicate_error import DuplicateError
from xoot.exceptions.integrity_violation_error import IntegrityViolationError
from xoot.models.event.write_context import WriteContext
from xoot.models.project.project import Project
from xoot.models.project.project_registration import ProjectRegistration
from xoot.services.project_service import add_alias, get_overview
from xoot.store.store import Store

KEY_WORDS = "an alias must not look like an item or decision key"


@pytest.mark.parametrize(
    "alias", ["goal-12", "batch-3", "subtask-1", "backlog-4", "decision-2x"]
)
def test_key_shaped_alias_is_refused_everywhere(
    store: Store, project: Project, ctx: WriteContext, row_counts: Any, alias: str
) -> None:
    """The model and the service say why in words; SQL refuses a raw insert."""
    before = row_counts()
    with pytest.raises(ValidationError) as model:
        ProjectRegistration(key_prefix="ab", name="n", aliases=(alias,))
    with pytest.raises(ValidationError) as service:
        add_alias(store, project.id, alias, ctx)
    with pytest.raises(IntegrityViolationError):
        with store.write() as conn:
            conn.execute(
                "INSERT INTO project_alias (alias, project_id) VALUES (?, ?)",
                (alias, project.id),
            )
    for caught in (model, service):
        assert caught.value.errors()[0]["msg"].startswith(KEY_WORDS)
    assert row_counts() == before


@pytest.mark.parametrize("alias", ["my-app", "a-b-c", "xoot-12", "goals-1"])
def test_dashed_alias_that_is_no_key_is_accepted(
    store: Store, project: Project, ctx: WriteContext, alias: str
) -> None:
    """The model accepts it, and add_alias stores it through the SQL check."""
    ProjectRegistration(key_prefix="ab", name="n", aliases=(alias,))
    add_alias(store, project.id, alias, ctx)
    assert alias in get_overview(store, project.id).aliases


def test_readding_an_own_alias_says_it_is_already_ours(
    store: Store, project: Project, ctx: WriteContext, row_counts: Any
) -> None:
    """The project's own alias is not reported as a clash with a project."""
    before = row_counts()
    with pytest.raises(DuplicateError) as caught:
        add_alias(store, project.id, "xo", ctx)
    assert str(caught.value) == "'xo' is already an alias of this project"
    assert row_counts() == before


def test_another_projects_alias_still_names_its_holder(
    store: Store, project: Project, other_project: Project, ctx: WriteContext
) -> None:
    """A clash with another project keeps the message naming that project."""
    with pytest.raises(DuplicateError) as caught:
        add_alias(store, other_project.id, "xo", ctx)
    assert str(caught.value) == (
        f"'xo' is already registered as an alias of project {project.key_prefix}"
    )
