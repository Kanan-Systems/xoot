"""
Project registration and naming: key prefix, aliases, paths and the default
workflow every new project starts with.
"""

import sqlite3

from pydantic import TypeAdapter

from xoot.exceptions.duplicate_error import DuplicateError
from xoot.models.event.actor import Actor
from xoot.models.event.event_action import EventAction
from xoot.models.event.write_context import WriteContext
from xoot.models.fields import AbsolutePath, Slug
from xoot.models.project.project import Project
from xoot.models.project.project_registration import ProjectRegistration
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.repositories.project import project_alias_db, project_db, project_path_db
from xoot.repositories.workflow import workflow_db
from xoot.services.id_checks import check_id
from xoot.services.lookups import require_project
from xoot.services.session_links import open_session_for
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store

_SLUG = TypeAdapter(Slug)
_PATH = TypeAdapter(AbsolutePath)


def register_project(
    store: Store, registration: ProjectRegistration, actor: Actor
) -> Project:
    """
    Create a project with the default workflow, its aliases and paths.

    Args:
        - store (Store): the database.
        - registration (ProjectRegistration): validated project details.
        - actor (Actor): who registers it. No session: sessions belong to
          projects, so none can exist yet.

    Returns:
        - project (Project): the new project, with its workflow active.

    Raises:
        - DuplicateError: the prefix, an alias or a path is already taken.
    """
    with store.write() as conn:
        if project_db.get_by_prefix(conn, registration.key_prefix) is not None:
            raise DuplicateError("key_prefix", registration.key_prefix)
        for alias in registration.aliases:
            _require_free_alias(conn, alias)
        for path in registration.paths:
            _require_free_path(conn, path)
        scope = WriteScope(conn, WriteContext(actor=actor))
        project = project_db.insert(
            conn, registration.key_prefix, registration.name, scope.now
        )
        workflow = workflow_db.insert(
            conn, project.id, 1, WorkflowDefinition.default(), scope.now
        )
        project = project_db.set_active_workflow(conn, project.id, workflow.id)
        scope.created(project)
        scope.created(workflow)
        for alias in registration.aliases:
            project_alias_db.insert(conn, alias, project.id)
            scope.noted(project, EventAction.ADD_ALIAS, {"alias": alias})
        for path in registration.paths:
            project_path_db.insert(conn, path, project.id)
            scope.noted(project, EventAction.ADD_PATH, {"path": path})
        return project


def add_alias(store: Store, project_id: int, alias: str, ctx: WriteContext) -> None:
    """
    Add a globally unique alias to a project.

    Args:
        - store (Store): the database.
        - project_id (int): project id.
        - alias (str): the alias; validated as a slug.
        - ctx (WriteContext): actor and optional session.

    Raises:
        - InvalidIdError: project_id is not an int id.
        - pydantic.ValidationError: the alias is not a valid slug.
        - DuplicateError: the alias is taken.
        - NotFoundError: no such project.
    """
    check_id("project_id", project_id)
    alias = _SLUG.validate_python(alias)
    with store.write() as conn:
        project = require_project(conn, project_id)
        open_session_for(conn, project_id, ctx.session_id)
        _require_free_alias(conn, alias)
        project_alias_db.insert(conn, alias, project_id)
        WriteScope(conn, ctx).noted(project, EventAction.ADD_ALIAS, {"alias": alias})


def add_path(store: Store, project_id: int, path: str, ctx: WriteContext) -> str:
    """
    Add a directory to a project.

    Args:
        - store (Store): the database.
        - project_id (int): project id.
        - path (str): an absolute path; normalized before storing.
        - ctx (WriteContext): actor and optional session.

    Returns:
        - path (str): the normalized path that was stored.

    Raises:
        - InvalidIdError: project_id is not an int id.
        - pydantic.ValidationError: the path is not absolute or too long.
        - DuplicateError: the path is taken.
        - NotFoundError: no such project.
    """
    check_id("project_id", project_id)
    path = _PATH.validate_python(path)
    with store.write() as conn:
        project = require_project(conn, project_id)
        open_session_for(conn, project_id, ctx.session_id)
        _require_free_path(conn, path)
        project_path_db.insert(conn, path, project_id)
        WriteScope(conn, ctx).noted(project, EventAction.ADD_PATH, {"path": path})
    return path


def get_project(store: Store, project_id: int) -> Project:
    """
    Fetch a project.

    Args:
        - store (Store): the database.
        - project_id (int): project id.

    Returns:
        - project (Project): the project.

    Raises:
        - InvalidIdError: project_id is not an int id.
        - NotFoundError: no such project.
    """
    check_id("project_id", project_id)
    with store.read() as conn:
        return require_project(conn, project_id)


def _require_free_alias(conn: sqlite3.Connection, alias: str) -> None:
    if project_alias_db.get(conn, alias) is not None:
        raise DuplicateError("alias", alias)


def _require_free_path(conn: sqlite3.Connection, path: str) -> None:
    if project_path_db.get(conn, path) is not None:
        raise DuplicateError("path", path)
