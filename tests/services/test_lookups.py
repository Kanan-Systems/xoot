"""Fetch-or-raise helpers: missing rows and cross-project rows."""

from collections.abc import Callable

import pytest

from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.exceptions.not_found_error import NotFoundError
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services.lookups import active_workflow, require_item, require_session
from xoot.store.store import Store


def test_missing_rows_raise_not_found(store: Store) -> None:
    """A missing id names the entity and the id."""
    with store.read() as conn:
        with pytest.raises(NotFoundError, match="item 7"):
            require_item(conn, 7)
        with pytest.raises(NotFoundError, match="session 8"):
            require_session(conn, 8)


def test_project_filter_rejects_other_projects(
    store: Store,
    project: Project,
    other_project: Project,
    make_item: Callable[..., Item],
) -> None:
    """With a project given, a row from another project is refused."""
    item = make_item(project, ItemKind.GOAL)
    with store.read() as conn:
        assert require_item(conn, item.id, project.id) == item
        with pytest.raises(CrossProjectError, match="xoot-1"):
            require_item(conn, item.id, other_project.id)


def test_project_without_workflow(store: Store, project: Project) -> None:
    """A project row with no active workflow is reported, not guessed at."""
    unfinished = project.model_copy(update={"active_workflow_id": None})
    with store.read() as conn:
        with pytest.raises(NotFoundError, match="active workflow"):
            active_workflow(conn, unfinished)
