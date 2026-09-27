"""The CLI spells out the key prefix and alias rules when it refuses a name."""

from typing import Any

import pytest


@pytest.mark.parametrize("prefix", ["ab-12", "a", "1ab", "Ab"])
def test_bad_prefix_error_is_in_words(xoot: Any, row_counts: Any, prefix: str) -> None:
    """The error states the rule, not a regular expression."""
    before = row_counts()
    run = xoot("init", "/work/new", "--prefix", prefix)
    assert (run.code, run.out) == (1, "")
    assert run.err == (
        "error: ValidationError: key_prefix: a key prefix is 2–32 lowercase "
        "letters or digits, starting with a letter; no dashes\n"
    )
    assert row_counts() == before


def test_key_shaped_alias_error_is_in_words(xoot: Any, row_counts: Any) -> None:
    """An alias that reads as a record key is refused with the reason."""
    before = row_counts()
    run = xoot("init", "/work/new", "--prefix", "ab", "--alias", "ab-s1")
    assert (run.code, run.out) == (1, "")
    assert run.err.startswith(
        "error: ValidationError: aliases.0: an alias must not look like an "
        "item, decision or session key"
    )
    assert row_counts() == before


@pytest.mark.usefixtures("project")
def test_readding_an_own_alias_through_the_cli(xoot: Any) -> None:
    """The CLI keeps the service's own-alias message."""
    run = xoot("project", "add-alias", "xo", "--project", "xoot")
    assert (run.code, run.out) == (1, "")
    assert run.err == (
        "error: DuplicateError: 'xo' is already an alias of this project\n"
    )
