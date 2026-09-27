"""Project registration, aliases and paths."""

from collections.abc import Callable

import pytest

from xoot.exceptions.duplicate_error import DuplicateError
from xoot.exceptions.integrity_violation_error import IntegrityViolationError
from xoot.exceptions.not_found_error import NotFoundError
from xoot.models.event.actor import Actor
from xoot.models.event.write_context import WriteContext
from xoot.models.project.project import Project
from xoot.models.project.project_registration import ProjectRegistration
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.services.project_service import add_alias, add_path, get_project
from xoot.services.project_service import register_project as register
from xoot.services.workflow_service import get_active_workflow
from xoot.store.store import Store


def test_registration_applies_the_default_workflow(
    store: Store, project: Project
) -> None:
    """A new project starts on version 1 of the shipped default."""
    workflow = get_active_workflow(store, project.id)
    assert project.active_workflow_id == workflow.id
    assert workflow.version == 1
    assert workflow.definition == WorkflowDefinition.default()
    assert (project.next_item_number, project.next_decision_number) == (1, 1)


@pytest.mark.usefixtures("project")
@pytest.mark.parametrize(
    ("registration", "field"),
    [
        (ProjectRegistration(key_prefix="xoot", name="again"), "key_prefix"),
        (ProjectRegistration(key_prefix="new", name="n", aliases=("xo",)), "alias"),
        (
            ProjectRegistration(key_prefix="new", name="n", paths=("/work/xoot/",)),
            "path",
        ),
    ],
)
def test_duplicates_are_rejected_without_writing(
    store: Store,
    user: Actor,
    row_counts: Callable[[], dict[str, int]],
    registration: ProjectRegistration,
    field: str,
) -> None:
    """A clash on prefix, alias or (normalized) path writes nothing."""
    before = row_counts()
    with pytest.raises(DuplicateError) as caught:
        register(store, registration, user)
    assert caught.value.field == field
    assert row_counts() == before


def test_add_alias_and_path(store: Store, project: Project, ctx: WriteContext) -> None:
    """Aliases must be unique; paths are normalized before storing."""
    add_alias(store, project.id, "xoot-cli", ctx)
    with pytest.raises(DuplicateError):
        add_alias(store, project.id, "xoot-cli", ctx)
    assert add_path(store, project.id, "/work//xoot-docs/", ctx) == "/work/xoot-docs"


def test_unknown_project(store: Store, ctx: WriteContext) -> None:
    """Writes and reads on a missing project raise NotFoundError."""
    with pytest.raises(NotFoundError):
        get_project(store, 999)
    with pytest.raises(NotFoundError):
        add_alias(store, 999, "zz", ctx)


def test_active_workflow_must_be_the_projects_own(
    store: Store, project: Project, other_project: Project
) -> None:
    """The composite foreign key refuses another project's workflow."""
    with pytest.raises(IntegrityViolationError, match="FOREIGN KEY"):
        with store.write() as conn:
            conn.execute(
                "UPDATE project SET active_workflow_id = ? WHERE id = ?",
                (other_project.active_workflow_id, project.id),
            )
