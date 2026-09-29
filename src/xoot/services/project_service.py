"""
Project registration and naming: key prefix, aliases, paths and the default
workflow every new project starts with.

Prefixes and aliases share one namespace (see project_names). Adding or
removing an alias or path is recorded as an event on the project.
"""

import sqlite3

from pydantic import TypeAdapter

from xoot.exceptions.not_found_error import NotFoundError
from xoot.models.event.actor import Actor
from xoot.models.event.event_action import EventAction
from xoot.models.event.write_context import WriteContext
from xoot.models.fields import Alias, ProjectDir, Slug
from xoot.models.project.project import Project
from xoot.models.project.project_overview import ProjectOverview
from xoot.models.project.project_registration import ProjectRegistration
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.repositories.project import project_alias_db, project_db, project_path_db
from xoot.repositories.workflow import workflow_db
from xoot.services.id_checks import check_id
from xoot.services.lookups import require_project
from xoot.services.project_names import (
    require_free_alias,
    require_free_path,
    require_free_prefix,
)
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store

_ALIAS = TypeAdapter(Alias)
_SLUG = TypeAdapter(Slug)
_DIR = TypeAdapter(ProjectDir)


def register_project(
    store: Store, registration: ProjectRegistration, actor: Actor
) -> Project:
    """
    Create a project with the default workflow, its aliases and paths.

    Args:
        - store (Store): the database.
        - registration (ProjectRegistration): validated project details; its
          paths exclude "/".
        - actor (Actor): who registers it.

    Returns:
        - project (Project): the new project, with its workflow active.

    Raises:
        - DuplicateError: the prefix or an alias already names a project,
          or a path is taken.
    """
    with store.write() as conn:
        require_free_prefix(conn, registration.key_prefix)
        for alias in registration.aliases:
            require_free_alias(conn, alias, None)
        for path in registration.paths:
            require_free_path(conn, path)
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
    Add an alias that names no other project.

    Args:
        - store (Store): the database.
        - project_id (int): project id.
        - alias (str): the alias; validated as a slug that does not look
          like a record key. It may equal this project's own prefix.
        - ctx (WriteContext): the actor.

    Raises:
        - InvalidIdError: project_id is not an int id.
        - pydantic.ValidationError: the alias is not a valid slug, or looks
          like an item or decision key.
        - DuplicateError: the alias is taken or is another project's prefix.
        - NotFoundError: no such project.
    """
    check_id("project_id", project_id)
    alias = _ALIAS.validate_python(alias)
    with store.write() as conn:
        project = require_project(conn, project_id)
        require_free_alias(conn, alias, project_id)
        project_alias_db.insert(conn, alias, project_id)
        WriteScope(conn, ctx).noted(project, EventAction.ADD_ALIAS, {"alias": alias})


def remove_alias(store: Store, project_id: int, alias: str, ctx: WriteContext) -> None:
    """
    Remove one of a project's aliases.

    Args:
        - store (Store): the database.
        - project_id (int): project id.
        - alias (str): the alias; validated as a slug.
        - ctx (WriteContext): the actor.

    Raises:
        - InvalidIdError: project_id is not an int id.
        - pydantic.ValidationError: the alias is not a valid slug.
        - NotFoundError: no such project, or the project has no such alias.
    """
    check_id("project_id", project_id)
    alias = _SLUG.validate_python(alias)
    with store.write() as conn:
        project = require_project(conn, project_id)
        if not project_alias_db.delete(conn, alias, project_id):
            raise NotFoundError("alias", alias)
        WriteScope(conn, ctx).noted(
            project, EventAction.REMOVE_ALIAS, {}, {"alias": alias}
        )


def add_path(store: Store, project_id: int, path: str, ctx: WriteContext) -> str:
    """
    Add a directory to a project.

    Args:
        - store (Store): the database.
        - project_id (int): project id.
        - path (str): an absolute path; normalized before storing.
        - ctx (WriteContext): the actor.

    Returns:
        - path (str): the normalized path that was stored.

    Raises:
        - InvalidIdError: project_id is not an int id.
        - pydantic.ValidationError: the path is not absolute, too long, or
          is "/" once normalized.
        - DuplicateError: the path is taken.
        - NotFoundError: no such project.
    """
    check_id("project_id", project_id)
    path = _DIR.validate_python(path)
    with store.write() as conn:
        project = require_project(conn, project_id)
        require_free_path(conn, path)
        project_path_db.insert(conn, path, project_id)
        WriteScope(conn, ctx).noted(project, EventAction.ADD_PATH, {"path": path})
    return path


def remove_path(store: Store, project_id: int, path: str, ctx: WriteContext) -> str:
    """
    Remove one of a project's directories.

    Args:
        - store (Store): the database.
        - project_id (int): project id.
        - path (str): an absolute path; normalized before matching.
        - ctx (WriteContext): the actor.

    Returns:
        - path (str): the normalized path that was removed.

    Raises:
        - InvalidIdError: project_id is not an int id.
        - pydantic.ValidationError: the path is not a valid project path.
        - NotFoundError: no such project, or the project has no such path.
    """
    check_id("project_id", project_id)
    path = _DIR.validate_python(path)
    with store.write() as conn:
        project = require_project(conn, project_id)
        if not project_path_db.delete(conn, path, project_id):
            raise NotFoundError("path", path)
        WriteScope(conn, ctx).noted(
            project, EventAction.REMOVE_PATH, {}, {"path": path}
        )
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


def get_overview(store: Store, project_id: int) -> ProjectOverview:
    """
    Fetch a project with its aliases and paths.

    Args:
        - store (Store): the database.
        - project_id (int): project id.

    Returns:
        - overview (ProjectOverview): the project, its aliases and paths.

    Raises:
        - InvalidIdError: project_id is not an int id.
        - NotFoundError: no such project.
    """
    check_id("project_id", project_id)
    with store.read() as conn:
        return overview(conn, require_project(conn, project_id))


def list_projects(store: Store) -> list[ProjectOverview]:
    """
    List every project with its aliases and paths, by key prefix.

    Args:
        - store (Store): the database.

    Returns:
        - projects (list[ProjectOverview]): all projects, from one snapshot.
    """
    with store.read() as conn:
        return [overview(conn, p) for p in project_db.list_all(conn)]


def overview(conn: sqlite3.Connection, project: Project) -> ProjectOverview:
    """
    Gather a project's aliases and paths.

    Args:
        - conn (sqlite3.Connection): a connection inside a transaction.
        - project (Project): the project.

    Returns:
        - overview (ProjectOverview): the project with its names and paths.
    """
    return ProjectOverview(
        project=project,
        aliases=tuple(project_alias_db.list_for_project(conn, project.id)),
        paths=tuple(project_path_db.list_for_project(conn, project.id)),
    )
