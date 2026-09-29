"""
Fixtures for the paste service tests: building pasted text, running it
through the parser and executor, and snapshotting the whole database.
"""

import hashlib
import json
from collections.abc import Callable
from typing import Any

import pytest

from xoot.services.paste.executor import apply, dry_run, result_digest
from xoot.services.paste.models.paste_result import PasteResult
from xoot.services.paste.parser import parse_paste
from xoot.store.store import Store

type Fenced = Callable[..., str]


@pytest.fixture(name="fenced")
def fixture_fenced() -> Fenced:
    """Factory: a chat reply holding one xoot block built from ops."""

    def build(ops: list[dict[str, Any]], **top: Any) -> str:
        block = {"xoot": 2, "project": "xoot", **top, "ops": ops}
        return f"Here you go:\n\n```xoot\n{json.dumps(block, indent=1)}\n```\n\nDone."

    return build


@pytest.fixture(name="paste")
def fixture_paste(store: Store) -> Callable[[str], PasteResult]:
    """Factory: parse, dry-run and apply a paste, as `xoot paste apply` does."""

    def run(text: str) -> PasteResult:
        block = parse_paste(text)
        return apply(store, block, result_digest(dry_run(store, block)))

    return run


@pytest.fixture(name="snapshot")
def fixture_snapshot(
    store: Store, row_counts: Callable[[], dict[str, int]]
) -> Callable[[], dict[str, Any]]:
    """
    Factory: everything a write could leave behind: row counts, a hash of
    the full dump, sqlite_sequence and the project rows holding the counters.
    """

    def take() -> dict[str, Any]:
        with store.read() as conn:
            dump = "\n".join(conn.iterdump())
            sequence = conn.execute(
                "SELECT name, seq FROM sqlite_sequence ORDER BY name"
            ).fetchall()
            projects = conn.execute("SELECT * FROM project ORDER BY id").fetchall()
        return {
            "counts": row_counts(),
            "dump": hashlib.sha256(dump.encode()).hexdigest(),
            "sequence": [tuple(row) for row in sequence],
            "projects": [tuple(row) for row in projects],
        }

    return take
