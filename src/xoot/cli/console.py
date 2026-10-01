"""
Where CLI output goes: results to stdout, everything else to stderr.

The streams are looked up on every call rather than captured once, so a
caller (or a test) that swaps sys.stdout, sys.stderr or sys.stdin is honoured.
"""

import sys
from collections.abc import Callable, Sequence

from pydantic import BaseModel

from xoot.cli.render.text import clean
from xoot.exceptions.confirmation_error import ConfirmationError

YES = frozenset({"y", "yes"})
# The controlling terminal, whatever stdin is: paste reads its payload from
# stdin, so the answer has to come from somewhere else.
TTY_PATH = "/dev/tty"


class Console:
    """
    Prints results as text or JSON, prints warnings and errors, and asks
    for confirmation before destructive commands.
    """

    def __init__(self, json_mode: bool) -> None:
        """
        Choose the result format.

        Args:
            - json_mode (bool): print results as JSON instead of text.
        """
        self.json_mode = json_mode

    def result[M: BaseModel](self, model: M, render: Callable[[M], str]) -> None:
        """
        Print a result to stdout.

        Args:
            - model (M): the result.
            - render (Callable[[M], str]): its text form, used without --json.
        """
        text = model.model_dump_json(indent=2) if self.json_mode else render(model)
        print(text, file=sys.stdout)

    @staticmethod
    def warn(message: str) -> None:
        """
        Print a warning to stderr.

        Args:
            - message (str): the warning, built from safe values.
        """
        print(f"warning: {message}", file=sys.stderr)

    @staticmethod
    def error(message: str) -> None:
        """
        Print an error line to stderr.

        Args:
            - message (str): the full line, e.g. "error: <Class>: <reason>".
        """
        print(message, file=sys.stderr)

    @staticmethod
    def confirm(changes: Sequence[str], yes: bool) -> None:
        """
        Show what is about to change and require a yes, unless --yes was given.

        Without a terminal on stdin nobody can answer, so the command is
        refused rather than guessed at.

        Args:
            - changes (Sequence[str]): one line per change. A line may name
              what changes (a key, a field, an alias, a project name, as a
              rename shows old and new), never an item's or decision's
              title or body.
            - yes (bool): --yes was given.

        Raises:
            - ConfirmationError: stdin is not a terminal, or the answer was
              not y/yes.
        """
        if yes:
            return
        if not sys.stdin.isatty():
            raise ConfirmationError("stdin is not a terminal; pass --yes to confirm")
        for line in changes:
            print(clean(line), file=sys.stderr)
        print("Proceed? [y/N] ", end="", file=sys.stderr, flush=True)
        if sys.stdin.readline().strip().lower() not in YES:
            raise ConfirmationError("aborted; nothing was written")

    @staticmethod
    def confirm_on_terminal(yes: bool) -> None:
        """
        Require a yes typed on the controlling terminal, unless --yes was given.

        The caller has already printed what will change. Without a
        controlling terminal nobody can answer, so the command is refused.

        Args:
            - yes (bool): --yes was given.

        Raises:
            - ConfirmationError: there is no controlling terminal, or the
              answer was not y/yes.
        """
        if yes:
            return
        try:
            terminal = open(TTY_PATH, encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ConfirmationError(
                "no controlling terminal to confirm on; pass --yes to confirm"
            ) from exc
        with terminal:
            print("Apply? [y/N] ", end="", file=sys.stderr, flush=True)
            answer = terminal.readline()
        if answer.strip().lower() not in YES:
            raise ConfirmationError("aborted; nothing was written")
