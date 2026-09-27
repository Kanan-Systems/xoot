"""
T6: workflow import, redact, remove-alias and remove-path ask first. Without
a terminal and without --yes they refuse; any answer but y/yes aborts; both
write nothing. The prompt names what changes, never redacted content.
"""

from pathlib import Path
from typing import Any

import pytest

from xoot.models.item.item import Item

CONFIRMED = {
    "workflow import": ["workflow", "import", "{toml}", "--project", "xo"],
    "redact": ["redact", "xoot-1", "body"],
    "remove-alias": ["project", "remove-alias", "xo", "--project", "xoot"],
    "remove-path": ["project", "remove-path", "/work/xoot", "--project", "xo"],
}
PROMPTS = {
    "workflow import": "import a new workflow into project xoot",
    "redact": "redact the body of item xoot-1",
    "remove-alias": "remove alias xo from project xoot",
    "remove-path": "remove path /work/xoot from project xoot",
}


def _argv(case: str, toml: Path) -> list[str]:
    return [part.format(toml=toml) for part in CONFIRMED[case]]


@pytest.mark.usefixtures("secret_item")
@pytest.mark.parametrize("case", list(CONFIRMED))
def test_no_terminal_without_yes_is_refused(
    xoot: Any, row_counts: Any, default_toml: Path, case: str
) -> None:
    """Nobody can answer, so nothing is asked and nothing is written."""
    before = row_counts()
    run = xoot(*_argv(case, default_toml))
    assert (run.code, run.out) == (1, "")
    assert run.err == (
        "error: ConfirmationError: stdin is not a terminal; pass --yes to confirm\n"
    )
    assert row_counts() == before


@pytest.mark.usefixtures("secret_item")
@pytest.mark.parametrize("answer", ["n", "", "no", "yess"])
@pytest.mark.parametrize("case", list(CONFIRMED))
def test_anything_but_yes_aborts(
    xoot: Any, row_counts: Any, default_toml: Path, case: str, answer: str
) -> None:
    """The prompt shows the change on stderr; a non-yes answer writes nothing."""
    before = row_counts()
    run = xoot(*_argv(case, default_toml), answer=answer)
    assert (run.code, run.out) == (1, "")
    assert PROMPTS[case] in run.err and "Proceed? [y/N] " in run.err
    assert run.err.endswith("error: ConfirmationError: aborted; nothing was written\n")
    assert row_counts() == before


@pytest.mark.usefixtures("secret_item")
@pytest.mark.parametrize("case", list(CONFIRMED))
def test_yes_applies(xoot: Any, row_counts: Any, default_toml: Path, case: str) -> None:
    """--yes applies without a prompt; answering y at a terminal does too."""
    before = row_counts()
    run = xoot(*_argv(case, default_toml), "--yes")
    assert (run.code, run.err) == (0, "")
    assert row_counts() != before


@pytest.mark.parametrize("answer", ["y", "YES", " yes "])
def test_answering_yes_applies(
    xoot: Any, secret_item: Item, answer: str, marker: str
) -> None:
    """The redaction prompt never contains the content it will remove."""
    run = xoot("redact", secret_item.key, "title", answer=answer)
    assert run.code == 0, run.err
    assert "redact the title of item xoot-1" in run.err
    assert marker not in run.err and marker not in run.out
