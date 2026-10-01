"""
Entry point for `xoot` and `python -m xoot.cli`.

Parses the arguments, opens the store and runs one command. Domain and
validation errors become one "error: <Class>: <reason>" line on stderr and
an exit code; anything unexpected is left to propagate.
"""

import sys
from collections.abc import Sequence

from pydantic import ValidationError

from xoot.cli import exit_codes
from xoot.cli.console import Console
from xoot.cli.parser import build_parser
from xoot.cli.render.errors import error_message, exit_code
from xoot.cli.render.text import clean
from xoot.exceptions.xoot_error import XootError
from xoot.store.paths import db_path_from_arg
from xoot.store.store import Store


def main(argv: Sequence[str] | None = None) -> int:
    """
    Run one xoot command.

    Args:
        - argv (Sequence[str] | None): arguments; sys.argv[1:] when None.

    Returns:
        - code (int): 0 success, 1 refused, 2 usage, 3 database unavailable.
    """
    try:
        args = build_parser().parse_args(argv)
        # A command's own usage rule that argparse cannot express.
        refine = getattr(args, "refine", None)
        if refine is not None:
            refine(args)
    except SystemExit as exc:
        # argparse exits 0 after --help and 2 on a usage error.
        return exit_codes.USAGE if exc.code not in (0, None) else exit_codes.OK
    console = Console(json_mode=args.json)
    try:
        store = Store.open(db_path_from_arg(args.db))
    except XootError as exc:
        console.error(error_message(exc))
        return exit_codes.UNAVAILABLE
    except OSError as exc:
        console.error(f"error: {type(exc).__name__}: {_os_reason(exc)}")
        return exit_codes.UNAVAILABLE
    with store:
        try:
            return int(args.handler(args, store, console))
        except (XootError, ValidationError) as exc:
            console.error(error_message(exc))
            return exit_code(exc)


def _os_reason(exc: OSError) -> str:
    """The OS's own reason, without the path it names."""
    return clean(exc.strerror or "the database file could not be created")


if __name__ == "__main__":
    sys.exit(main())
