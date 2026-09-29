"""Helpers every command shares: the CLI write context and project lookup."""

import argparse
import os
from collections.abc import Iterable

from pydantic import validate_call

from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client
from xoot.models.event.write_context import WriteContext
from xoot.models.fields import Alias, ProjectDir
from xoot.models.project.project import Project
from xoot.server.schemas.literals import ResolvedBy
from xoot.services.project_resolver import resolve_project
from xoot.services.project_scope import key_qualifier
from xoot.store.store import Store

USER = Actor(kind=ActorKind.USER, client=Client.CLI)
# Every CLI write is the user's, through the cli client.
WRITE = WriteContext(actor=USER)


def project_of(
    args: argparse.Namespace, store: Store, keys: Iterable[str | None] = ()
) -> tuple[Project, ResolvedBy]:
    """
    Resolve the command's project: --project, else the keys' "<prefix>:"
    qualifier, else the working directory.

    Args:
        - args (argparse.Namespace): parsed arguments with a project field.
        - store (Store): the database.
        - keys (Iterable[str | None]): the command's key arguments.

    Returns:
        - resolved (tuple[Project, ResolvedBy]): the project, and "prefix",
          "alias", "qualified" or "cwd" for how it was found.

    Raises:
        - ProjectResolutionError: nothing matched.
        - QualifierError: the keys name different projects, or another
          project than --project.
    """
    qualifier = key_qualifier(keys)
    return resolve_project(store, args.project, working_directory(), qualifier)


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


@validate_call
def project_dir(path: ProjectDir) -> str:
    """
    Validate a command's directory argument as a project directory.

    Validating here rather than inside the service labels a refusal "path"
    in the error line, the name the user knows the argument by.

    Args:
        - path (ProjectDir): an absolute path; pass it by keyword, so a
          refusal is located at "path".

    Returns:
        - path (str): the normalized path.

    Raises:
        - pydantic.ValidationError: the path is not absolute, too long, or
          is "/" once normalized.
    """
    return path


@validate_call
def alias_arg(alias: Alias) -> str:
    """
    Validate a command's alias argument as a new alias.

    Validating here rather than inside the service labels a refusal "alias"
    in the error line, the name the user knows the argument by.

    Args:
        - alias (Alias): the alias; pass it by keyword, so a refusal is
          located at "alias".

    Returns:
        - alias (str): the same alias.

    Raises:
        - pydantic.ValidationError: the alias is not a slug, or looks like
          a key.
    """
    return alias
