"""
`project add-alias` reports an invalid alias at "alias:", the name the user
knows the argument by, not at a generic "input:".
"""

from typing import Any

import pytest


@pytest.mark.usefixtures("project")
@pytest.mark.parametrize(
    ("alias", "reason"),
    [
        ("Bad!", "String should match pattern '^[a-z][a-z0-9-]{1,31}$'"),
        (
            "goal-12",
            "an alias must not look like an item or decision key (a kind, a "
            "dash, then a number, such as goal-12, backlog-3 or decision-1)",
        ),
    ],
)
def test_invalid_alias_is_located_at_alias(
    xoot: Any, row_counts: Any, alias: str, reason: str
) -> None:
    """The error line names the alias argument; nothing is written."""
    before = row_counts()
    run = xoot("project", "add-alias", alias, "--project", "xoot")
    assert (run.code, run.out) == (1, "")
    assert run.err == f"error: ValidationError: alias: {reason}\n"
    assert row_counts() == before
