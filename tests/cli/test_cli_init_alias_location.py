"""
`xoot init --alias` reports an invalid alias at "alias:", like add-alias,
not at the registration's "aliases.<n>".
"""

from pathlib import Path
from typing import Any

import pytest


@pytest.mark.parametrize(
    ("aliases", "reason"),
    [
        (["ok", "Bad!"], "String should match pattern '^[a-z][a-z0-9-]{1,31}$'"),
        (
            ["goal-12"],
            "an alias must not look like an item or decision key (a kind, a "
            "dash, then a number, such as goal-12, backlog-3 or decision-1)",
        ),
    ],
)
def test_invalid_init_alias_is_located_at_alias(
    xoot: Any, row_counts: Any, tmp_path: Path, aliases: list[str], reason: str
) -> None:
    """The error line names the alias argument; no project is registered."""
    before = row_counts()
    flags = [part for alias in aliases for part in ("--alias", alias)]
    run = xoot("init", str(tmp_path), "--prefix", "xoot", *flags)
    assert (run.code, run.out) == (1, "")
    assert run.err == f"error: ValidationError: alias: {reason}\n"
    assert row_counts() == before
