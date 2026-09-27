"""Helpers every command shares: the CLI write context and project lookup."""

import argparse
import os

from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.write_context import WriteContext
from xoot.models.project.project import Project
from xoot.models.session.client import Client
from xoot.server.schemas.literals import ResolvedBy
from xoot.services.project_resolver import resolve_project
from xoot.store.store import Store

USER = Actor(kind=ActorKind.USER, client=Client.CLI)
# Every CLI write is the user's, through the cli client, outside any session.
WRITE = WriteContext(actor=USER)


def project_of(args: argparse.Namespace, store: Store) -> tuple[Project, ResolvedBy]:
    """
    Resolve the command's project: --project, else the working directory.

    Args:
        - args (argparse.Namespace): parsed arguments with a project field.
        - store (Store): the database.

    Returns:
        - resolved (tuple[Project, ResolvedBy]): the project, and "alias" or
          "cwd" for how it was found.

    Raises:
        - ProjectResolutionError: nothing matched.
    """
    project = resolve_project(store, args.project, working_directory())
    return project, "cwd" if args.project is None else "alias"


def working_directory() -> str:
    """
    Return the current directory, or "" when it no longer exists.

    Returns:
        - path (str): an absolute path, or "" (which resolves to nothing).
    """
    try:
        return os.getcwd()
    except OSError:
        return ""


def absolute(path: str) -> str:
    """
    Make a command-line path absolute against the working directory.

    Lexical only, like every stored path: nothing is opened or resolved.

    Args:
        - path (str): the path as typed.

    Returns:
        - path (str): an absolute, normalized path.
    """
    return os.path.abspath(path)
