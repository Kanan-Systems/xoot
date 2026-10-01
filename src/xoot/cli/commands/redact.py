"""`xoot redact`: clear a free-text field from a record and its history."""

import argparse
import re

from xoot.cli import exit_codes
from xoot.cli.commands.common import ALIAS_HINT, USER, project_of
from xoot.cli.console import Console
from xoot.cli.render.results import render_redaction
from xoot.models.event.entity_type import EntityType
from xoot.models.event.redactable_field import RedactableField
from xoot.models.project.project import Project
from xoot.services import project_service
from xoot.services.key_resolver import entity_by_key, project_by_key
from xoot.services.project_scope import unqualified
from xoot.services.redaction_service import redact_field, redaction_target
from xoot.store.store import Store
from xoot.utils.keys import PREFIX_KEY

PURGE_HINT = (
    "the redaction is committed, but another client kept the WAL from being "
    "truncated, so old text may remain on disk; close clients such as "
    "xoot-mcp and redo the redaction"
)


def run_redact(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Redact FIELD of the record KEY names, after confirmation.

    KEY is an item or decision key (qualified as <prefix>:<key>, or in the
    project --project or the working directory selects), or a bare key
    prefix, which names the project itself. The prompt names the key and
    the field, never the content. A redacted project name leaves its
    aliases in place; a warning lists the ones to consider removing.

    Args:
        - args (argparse.Namespace): the key, the field, --project and --yes.
        - store (Store): the database.
        - console (Console): output and the confirmation prompt.

    Returns:
        - code (int): OK, or UNAVAILABLE when the purge did not complete.

    Raises:
        - NotFoundError: the key names nothing.
        - ProjectResolutionError: a key's project could not be found.
        - RedactionError: the record has no such field, or it is empty.
        - ConfirmationError: the redaction was not confirmed.
    """
    named: Project | None = None
    if PREFIX_KEY.fullmatch(args.key) is not None:
        with store.read() as conn:
            named = project_by_key(conn, args.key)
        entity_type, entity_id = EntityType.PROJECT, named.id
    else:
        project, _ = project_of(args, store, [args.key])
        with store.read() as conn:
            entity_type, entity_id = entity_by_key(
                conn, project.id, unqualified(args.key)
            )
    redaction_target(entity_type, args.field)
    console.confirm(
        [
            f"redact the {args.field} of {entity_type} {args.key}",
            "the record and its history are rewritten; this cannot be undone",
        ],
        args.yes,
    )
    result = redact_field(store, entity_type, entity_id, args.field, USER)
    console.result(result, lambda r: render_redaction(r, args.key))
    if named is not None and args.field == RedactableField.NAME:
        _warn_aliases(store, named, console)
    if not result.purged:
        console.warn(PURGE_HINT)
        return exit_codes.UNAVAILABLE
    return exit_codes.OK


def name_slug(name: str) -> str:
    """
    Spell a display name the way an alias would: lowercase, words joined by
    hyphens.

    Args:
        - name (str): a project name.

    Returns:
        - slug (str): e.g. "kroot site" -> "kroot-site", "[redacted]" ->
          "redacted".
    """
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _warn_aliases(store: Store, before: Project, console: Console) -> None:
    """
    After a name redaction, name the aliases that may still spell it.

    Those equal to the slug of the old or the new name; every alias when
    none is. Nothing is removed: the user decides.
    """
    overview = project_service.get_overview(store, before.id)
    spelled = {name_slug(before.name), name_slug(overview.project.name)}
    matching = [alias for alias in overview.aliases if alias in spelled]
    listed = matching or list(overview.aliases)
    if not listed:
        return
    console.warn(ALIAS_HINT)
    prefix = overview.project.key_prefix
    for alias in listed:
        console.warn(
            f"alias {alias}: xoot project remove-alias {alias} --project {prefix}"
        )
