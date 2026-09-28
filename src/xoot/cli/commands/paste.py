"""
`xoot paste`: print the paste brief, or apply one xoot block from a chat.

apply reads the block from a file or stdin (at most 256 KiB), dry-runs it,
prints the plan to stderr, with a warning section when a title or body
looks damaged by a clipboard code page, and asks y/N on the controlling
terminal, since stdin may be carrying the paste. The apply re-runs the block and commits
only if it does exactly what the plan showed. Every write is Claude's,
through client paste.
"""

import argparse
import os
import stat
import sys
from pathlib import Path

from xoot.cli import exit_codes
from xoot.cli.commands.common import absolute, project_of
from xoot.cli.console import Console
from xoot.cli.render.paste import encoding_lines, plan_lines, render_receipt
from xoot.cli.render.paste_brief import render_paste_brief
from xoot.cli.schemas.paste_brief_output import PasteBriefOutput
from xoot.exceptions.paste_error import PasteError
from xoot.server.brief import build_brief
from xoot.services.paste.encoding_check import encoding_warnings
from xoot.services.paste.executor import apply, dry_run, result_digest
from xoot.services.paste.parser import MAX_BYTES, decode_paste, parse_paste
from xoot.store.store import Store

STDIN = "-"
NOT_A_FILE = "the paste source is not a regular file or a pipe"


def run_brief(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Print the paste brief of the resolved project.

    Args:
        - args (argparse.Namespace): the optional --project.
        - store (Store): the database.
        - console (Console): output.

    Returns:
        - code (int): OK.

    Raises:
        - ProjectResolutionError: no project matched.
    """
    project, resolved_by = project_of(args, store)
    with store.read() as conn:
        brief = build_brief(conn, project, resolved_by, store.path)
    output = render_paste_brief(brief)
    console.result(output, _markdown)
    return exit_codes.OK


def run_apply(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Dry-run a pasted block, confirm its plan, then apply it.

    Args:
        - args (argparse.Namespace): the source and --yes.
        - store (Store): the database.
        - console (Console): output and the terminal confirmation.

    Returns:
        - code (int): OK.

    Raises:
        - PasteError: the source is unreadable, too large, not UTF-8, holds
          no single valid block, or the plan changed before the apply.
        - PasteOpError: an op failed; nothing was written.
        - ConfirmationError: the plan was not confirmed.
    """
    block = parse_paste(decode_paste(read_source(args.source)))
    warnings = encoding_warnings(block)
    preview = dry_run(store, block)
    for line in [*plan_lines(preview), *encoding_lines(warnings)]:
        print(line, file=sys.stderr)
    console.confirm_on_terminal(args.yes)
    applied = apply(store, block, result_digest(preview))
    console.result(applied.model_copy(update={"warnings": warnings}), render_receipt)
    return exit_codes.OK


def read_source(source: str) -> bytes:
    """
    Read at most MAX_BYTES + 1 bytes from a file, a pipe, or stdin ("-").

    One byte past the cap is read so the decoder can refuse an oversized
    paste without reading the rest of it.

    Args:
        - source (str): a path, or "-" for stdin.

    Returns:
        - data (bytes): the bytes read.

    Raises:
        - PasteError: the path is not a regular file or a pipe, or cannot
          be read.
    """
    if source == STDIN:
        try:
            return sys.stdin.buffer.read(MAX_BYTES + 1)
        except OSError as exc:
            raise PasteError("stdin could not be read") from exc
    try:
        with Path(absolute(source)).open("rb") as handle:
            mode = os.fstat(handle.fileno()).st_mode
            if not (stat.S_ISREG(mode) or stat.S_ISFIFO(mode)):
                raise PasteError(NOT_A_FILE)
            return handle.read(MAX_BYTES + 1)
    except IsADirectoryError as exc:
        raise PasteError(NOT_A_FILE) from exc
    except OSError as exc:
        raise PasteError("the paste source could not be read") from exc


def _markdown(output: PasteBriefOutput) -> str:
    return output.markdown.rstrip("\n")
