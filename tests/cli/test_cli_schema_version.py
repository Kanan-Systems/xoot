"""The CLI refuses a database newer than the code's SCHEMA_VERSION."""

from collections.abc import Callable
from typing import Any

from xoot.cli import exit_codes
from xoot.store.migrator import SCHEMA_VERSION


def test_cli_refuses_a_newer_database(
    xoot: Any, newer_database: Callable[[], int]
) -> None:
    """Exit code and line are those of every SchemaVersionError."""
    found = newer_database()
    run = xoot("db", "stats")
    assert run.code == exit_codes.UNAVAILABLE
    assert run.out == ""
    assert run.err == (
        f"error: SchemaVersionError: database schema version {found} "
        f"is newer than supported {SCHEMA_VERSION}\n"
    )
