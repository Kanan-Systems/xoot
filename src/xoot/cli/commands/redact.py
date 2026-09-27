"""`xoot redact`: clear a free-text field from a record and its history."""

import argparse

from xoot.cli import exit_codes
from xoot.cli.commands.common import USER
from xoot.cli.console import Console
from xoot.cli.render.results import render_redaction
from xoot.services.key_resolver import entity_by_key
from xoot.services.redaction_service import redact_field, redaction_target
from xoot.store.store import Store

PURGE_HINT = (
    "the redaction is committed, but another client kept the WAL from being "
    "truncated, so old text may remain on disk; close clients such as "
    "xoot-mcp and redo the redaction"
)


def run_redact(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Redact FIELD of the record KEY names, after confirmation.

    KEY with a dash is an item, decision or session key; without one it is
    a project prefix. The prompt names the key and the field, never the
    content.

    Args:
        - args (argparse.Namespace): the key, the field and --yes.
        - store (Store): the database.
        - console (Console): output and the confirmation prompt.

    Returns:
        - code (int): OK, or UNAVAILABLE when the purge did not complete.

    Raises:
        - NotFoundError: the key names nothing.
        - RedactionError: the record has no such field, or it is empty.
        - ConfirmationError: the redaction was not confirmed.
    """
    with store.read() as conn:
        entity_type, entity_id = entity_by_key(conn, args.key)
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
