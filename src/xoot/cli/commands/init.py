"""`xoot init`: register a project for a directory."""

import argparse

from xoot.cli import exit_codes
from xoot.cli.commands.common import USER, absolute, working_directory
from xoot.cli.console import Console
from xoot.cli.render.projects import render_project
from xoot.models.project.project_registration import ProjectRegistration
from xoot.server.brief import project_entry
from xoot.services.project_service import get_overview, register_project
from xoot.store.store import Store


def run_init(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Register a project at PATH (default: the working directory).

    Args:
        - args (argparse.Namespace): path, prefix, name and aliases.
        - store (Store): the database.
        - console (Console): output.

    Returns:
        - code (int): OK.

    Raises:
        - pydantic.ValidationError: the prefix, name, an alias or the path
          is invalid (the path may not be "/").
        - DuplicateError: the prefix or an alias already names a project,
          or the path is taken.
    """
    path = working_directory() if args.path is None else absolute(args.path)
    registration = ProjectRegistration(
        key_prefix=args.prefix,
        name=args.prefix if args.name is None else args.name,
        aliases=tuple(args.alias),
        paths=(path,),
    )
    project = register_project(store, registration, USER)
    console.result(project_entry(get_overview(store, project.id)), render_project)
    return exit_codes.OK
