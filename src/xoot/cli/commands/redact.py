"""`xoot redact`: clear a free-text field from a record and its history."""

import argparse

from xoot.cli import exit_codes
from xoot.cli.commands.common import USER, project_of
from xoot.cli.console import Console
from xoot.cli.render.results import render_redaction
from xoot.models.event.entity_type import EntityType
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
    the field, never the content.

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
    if PREFIX_KEY.fullmatch(args.key) is not None:
        with store.read() as conn:
            entity_type, entity_id = (
                EntityType.PROJECT,
                project_by_key(conn, args.key).id,
            )
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
    if not result.purged:
        console.warn(PURGE_HINT)
        return exit_codes.UNAVAILABLE
    return exit_codes.OK
