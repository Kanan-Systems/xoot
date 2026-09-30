"""`xoot project`: list, show, rename, and add or remove aliases and paths."""

import argparse

from xoot.cli import exit_codes
from xoot.cli.commands.common import (
    WRITE,
    absolute,
    alias_arg,
    name_arg,
    project_dir,
    project_of,
)
from xoot.cli.console import Console
from xoot.cli.render.projects import render_project, render_project_list
from xoot.exceptions.not_found_error import NotFoundError
from xoot.server.brief import project_entry
from xoot.server.schemas.projects_list_output import ProjectsListOutput
from xoot.services import project_service
from xoot.store.store import Store


def run_list(_args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    List every project with its aliases and paths.

    Args:
        - _args (argparse.Namespace): unused.
        - store (Store): the database.
        - console (Console): output.

    Returns:
        - code (int): OK.
    """
    projects = [project_entry(p) for p in project_service.list_projects(store)]
    output = ProjectsListOutput(db_path=str(store.path), projects=projects)
    console.result(output, render_project_list)
    return exit_codes.OK


def run_show(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Show the resolved project.

    Args:
        - args (argparse.Namespace): the optional --project.
        - store (Store): the database.
        - console (Console): output.

    Returns:
        - code (int): OK.

    Raises:
        - ProjectResolutionError: no project matched.
    """
    project, _ = project_of(args, store)
    return _show(store, project.id, console)


def run_add_alias(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Add an alias to the resolved project.

    Args:
        - args (argparse.Namespace): the alias and the optional --project.
        - store (Store): the database.
        - console (Console): output.

    Returns:
        - code (int): OK.

    Raises:
        - ProjectResolutionError: no project matched.
        - pydantic.ValidationError: the alias is not a valid slug.
        - DuplicateError: the alias already names a project.
    """
    project, _ = project_of(args, store)
    alias = alias_arg(alias=args.alias)
    project_service.add_alias(store, project.id, alias, WRITE)
    return _show(store, project.id, console)


def run_remove_alias(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Remove one of the resolved project's aliases, after confirmation.

    Args:
        - args (argparse.Namespace): the alias, --project and --yes.
        - store (Store): the database.
        - console (Console): output and the confirmation prompt.

    Returns:
        - code (int): OK.

    Raises:
        - ProjectResolutionError: no project matched.
        - NotFoundError: the project has no such alias.
        - ConfirmationError: the removal was not confirmed.
    """
    project, _ = project_of(args, store)
    if args.alias not in project_service.get_overview(store, project.id).aliases:
        raise NotFoundError("alias", args.alias)
    console.confirm(
        [f"remove alias {args.alias} from project {project.key_prefix}"], args.yes
    )
    project_service.remove_alias(store, project.id, args.alias, WRITE)
    return _show(store, project.id, console)


def run_add_path(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Add a directory to the resolved project.

    Args:
        - args (argparse.Namespace): the path and the optional --project.
        - store (Store): the database.
        - console (Console): output.

    Returns:
        - code (int): OK.

    Raises:
        - ProjectResolutionError: no project matched.
        - pydantic.ValidationError: the path is "/" or too long.
        - DuplicateError: the path is taken.
    """
    project, _ = project_of(args, store)
    path = project_dir(path=absolute(args.path))
    project_service.add_path(store, project.id, path, WRITE)
    return _show(store, project.id, console)


def run_remove_path(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Remove one of the resolved project's directories, after confirmation.

    Args:
        - args (argparse.Namespace): the path, --project and --yes.
        - store (Store): the database.
        - console (Console): output and the confirmation prompt.

    Returns:
        - code (int): OK.

    Raises:
        - ProjectResolutionError: no project matched.
        - NotFoundError: the project has no such path.
        - ConfirmationError: the removal was not confirmed.
    """
    project, _ = project_of(args, store)
    path = absolute(args.path)
    if path not in project_service.get_overview(store, project.id).paths:
        raise NotFoundError("path", path)
    console.confirm([f"remove path {path} from project {project.key_prefix}"], args.yes)
    project_service.remove_path(store, project.id, path, WRITE)
    return _show(store, project.id, console)


def run_rename(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Rename a project and/or add an alias, after confirmation.

    Only the display name changes; the key prefix, and so every key, stays.

    Args:
        - args (argparse.Namespace): the project, --name, --alias and --yes.
        - store (Store): the database.
        - console (Console): output and the confirmation prompt.

    Returns:
        - code (int): OK, or USAGE when neither --name nor --alias is given.

    Raises:
        - ProjectResolutionError: no project matched.
        - pydantic.ValidationError: the name or the alias is invalid.
        - DuplicateError: the alias already names a project.
        - ConfirmationError: the rename was not confirmed.
    """
    if args.name is None and args.alias is None:
        console.error("error: pass --name, --alias or both")
        return exit_codes.USAGE
    project, _ = project_of(args, store)
    name = None if args.name is None else name_arg(name=args.name)
    alias = None if args.alias is None else alias_arg(alias=args.alias)
    changes = []
    if name is not None:
        changes.append(
            f"rename project {project.key_prefix}: {project.name!r} -> {name!r}"
        )
    if alias is not None:
        changes.append(f"add alias {alias} to project {project.key_prefix}")
    console.confirm(changes, args.yes)
    project_service.rename_project(store, project.id, name, alias, WRITE)
    return _show(store, project.id, console)


def _show(store: Store, project_id: int, console: Console) -> int:
    overview = project_service.get_overview(store, project_id)
    console.result(project_entry(overview), render_project)
    return exit_codes.OK
