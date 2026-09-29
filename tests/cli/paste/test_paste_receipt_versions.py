"""
The receipt lists every item whose version the block changed, including the
batch and goal the completion engine closed, and a follow-up block built
from those versions applies cleanly.
"""

from collections.abc import Callable
from typing import Any

import pytest


@pytest.mark.usefixtures("project")
def test_engine_writes_are_in_the_receipt(
    paste_cli: Callable[..., Any], reply: Callable[..., bytes]
) -> None:
    """A block that completes a batch and a goal lists both, then reuses them."""
    block_a = [
        {"op": "item_create", "ref": "report", "kind": "goal", "title": "report"},
        {"op": "item_create", "ref": "pdf", "kind": "batch", "title": "pdf",
         "parent": "$report"},
        {"op": "item_create", "ref": "pages", "kind": "subtask",
         "title": "pages", "parent": "$pdf"},
    ]  # fmt: skip
    run_a = paste_cli("paste", "apply", "-", "--yes", stdin=reply(block_a))
    assert run_a.code == 0, run_a.err

    block_b = [
        {"op": "item_update", "key": "goal-1/batch-1/subtask-1",
         "expected_version": 1, "changes": {"state": "done"}},
    ]  # fmt: skip
    run_b = paste_cli("paste", "apply", "-", "--yes", stdin=reply(block_b))
    assert run_b.code == 0, run_b.err
    receipt = run_b.receipt()
    assert receipt["completed"] == ["goal-1/batch-1", "goal-1"]
    assert receipt["items"] == [
        {"key": "goal-1/batch-1/subtask-1", "version": 2, "state": "done"},
        {"key": "goal-1/batch-1", "version": 2, "state": "done"},
        {"key": "goal-1", "version": 2, "state": "done"},
    ]
    versions = {item["key"]: item["version"] for item in receipt["items"]}

    block_c = [
        {"op": "item_update", "key": "goal-1/batch-1",
         "expected_version": versions["goal-1/batch-1"],
         "changes": {"title": "pdf writer"}},
        {"op": "item_update", "key": "goal-1",
         "expected_version": versions["goal-1"], "changes": {"title": "pdf report"}},
    ]  # fmt: skip
    run_c = paste_cli("paste", "apply", "-", "--yes", stdin=reply(block_c))
    assert run_c.code == 0, run_c.err
    assert run_c.receipt()["items"] == [
        {"key": "goal-1/batch-1", "version": 3, "state": "done"},
        {"key": "goal-1", "version": 3, "state": "done"},
    ]
