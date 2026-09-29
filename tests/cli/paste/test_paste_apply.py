"""
`xoot paste apply`: the source is read within the cap, the plan goes to
stderr with a COMPLETION section, and after confirmation stdout gets a
xoot-receipt block that maps refs to keys and never holds titles or bodies.
"""

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from xoot.models.project.project import Project
from xoot.repositories.item import item_db
from xoot.services.paste.parser import MAX_BYTES
from xoot.store.store import Store

MARKER = "receipt-secret-0b9e"
OPS = [
    {"op": "item_create", "ref": "g", "kind": "goal", "title": f"g {MARKER}"},
    {
        "op": "item_create",
        "ref": "b",
        "kind": "batch",
        "title": "b",
        "body": f"body {MARKER}",
        "parent": "$g",
    },
    {"op": "item_update", "key": "$b", "changes": {"state": "active"}},
    {
        "op": "decision_record",
        "ref": "d",
        "owner": "$g",
        "title": f"d {MARKER}",
        "body": MARKER,
        "status": "locked",
    },
]


@pytest.mark.usefixtures("project")
def test_yes_applies_and_prints_the_plan_on_stderr(
    paste_cli: Callable[..., Any], reply: Callable[..., bytes]
) -> None:
    """The plan names every op and its changes; stdout holds only the receipt."""
    run = paste_cli("paste", "apply", "-", "--yes", stdin=reply(OPS))
    assert run.code == 0, run.err
    assert run.err.splitlines() == [
        "paste plan: project xoot",
        f'  op 1 item_create: goal-1 (new, $g) goal "g {MARKER}"',
        '  op 2 item_create: goal-1/batch-1 (new, $b) batch "b"',
        '  op 3 item_update: goal-1/batch-1 batch "b"',
        "      goal-1/batch-1 state: open -> active",
        f'  op 4 decision_record: goal-1/decision-1 (new, $d) decision "d {MARKER}"',
        "COMPLETION",
        "  (none)",
    ]
    assert run.out.startswith("```xoot-receipt\n")


@pytest.mark.usefixtures("project")
def test_receipt_maps_refs_and_holds_no_text(
    paste_cli: Callable[..., Any],
    reply: Callable[..., bytes],
    store: Store,
    project: Project,
) -> None:
    """The receipt parses, its keys are real, and no title or body leaks."""
    run = paste_cli("paste", "apply", "-", "--yes", stdin=reply(OPS))
    receipt = run.receipt()
    assert receipt == {
        "xoot": 2,
        "project": "xoot",
        "refs": {"g": "goal-1", "b": "goal-1/batch-1", "d": "goal-1/decision-1"},
        "items": [
            {"key": "goal-1", "version": 1, "state": "open"},
            {"key": "goal-1/batch-1", "version": 2, "state": "active"},
        ],
        "decisions": [{"key": "goal-1/decision-1", "version": 1, "status": "locked"}],
        "completed": [],
        "reopened": [],
        "blocked": [],
    }
    with store.read() as conn:
        batch = item_db.get_by_key(conn, project.id, receipt["refs"]["b"])
    assert batch is not None and batch.version == 2
    # Titles are named in the plan on stderr; bodies never appear anywhere.
    assert MARKER not in run.out and f"body {MARKER}" not in run.err


@pytest.mark.usefixtures("project")
def test_receipt_piped_back_is_ignored(
    paste_cli: Callable[..., Any],
    reply: Callable[..., bytes],
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """A receipt is not an xoot block: pasting it back writes nothing."""
    receipt = paste_cli("paste", "apply", "-", "--yes", stdin=reply(OPS)).out
    before = row_counts()
    run = paste_cli("paste", "apply", "-", "--yes", stdin=receipt.encode())
    assert (run.code, run.out) == (1, "")
    assert run.err == "error: PasteError: no xoot block found\n"
    assert row_counts() == before


@pytest.mark.usefixtures("project")
def test_json_prints_the_paste_result(
    paste_cli: Callable[..., Any], reply: Callable[..., bytes]
) -> None:
    """--json prints the full result instead of the receipt."""
    run = paste_cli("paste", "apply", "-", "--yes", "--json", stdin=reply(OPS))
    result = json.loads(run.out)
    assert [o["op"] for o in result["outcomes"]][:2] == ["item_create", "item_create"]
    assert result["refs"]["g"] == "goal-1" and result["completed"] == []
    assert MARKER not in run.out


@pytest.mark.usefixtures("project")
def test_tty_answer_applies_and_no_writes_nothing(
    paste_cli: Callable[..., Any],
    reply: Callable[..., bytes],
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """The answer is read from the terminal stand-in, not from stdin."""
    before = row_counts()
    refused = paste_cli("paste", "apply", "-", stdin=reply(OPS), answer="n")
    assert refused.code == 1 and row_counts() == before
    applied = paste_cli("paste", "apply", "-", stdin=reply(OPS), answer="y")
    assert applied.code == 0 and "Apply? [y/N] " in applied.err


@pytest.mark.usefixtures("project")
def test_no_terminal_and_no_yes_is_refused(
    paste_cli: Callable[..., Any],
    reply: Callable[..., bytes],
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """Without a terminal the plan is shown, then the command refuses."""
    before = row_counts()
    run = paste_cli("paste", "apply", "-", stdin=reply(OPS))
    assert (run.code, run.out) == (1, "")
    assert "paste plan:" in run.err and "ConfirmationError" in run.err
    assert row_counts() == before


def test_completion_section_lists_what_the_block_completes(
    paste_cli: Callable[..., Any],
    reply: Callable[..., bytes],
    work_tree: tuple[Any, Any, Any, Any],
    capture_on: Callable[..., Any],
) -> None:
    """Blocked goals and batches, and completions, are named on the plan."""
    _, _, first, second = work_tree
    capture_on(first)
    ops = [
        {"op": "item_update", "key": item.key, "expected_version": 1,
         "changes": {"state": "done"}}
        for item in (first, second)
    ]  # fmt: skip
    run = paste_cli("paste", "apply", "-", "--yes", stdin=reply(ops))
    assert run.code == 0, run.err
    lines = run.err.splitlines()
    assert lines[lines.index("COMPLETION") + 1 :] == [
        "  goal-1/batch-1 stays open: 1 open backlog item(s)"
    ]
    assert run.receipt()["blocked"] == [{"key": "goal-1/batch-1", "open_backlog": 1}]


@pytest.mark.usefixtures("project")
def test_file_source_is_read(
    paste_cli: Callable[..., Any], reply: Callable[..., bytes], tmp_path: Path
) -> None:
    """A regular file works like stdin."""
    source = tmp_path / "reply.md"
    source.write_bytes(reply(OPS))
    assert paste_cli("paste", "apply", str(source), "--yes").code == 0


@pytest.mark.usefixtures("project")
def test_fifo_source_is_read(
    paste_cli: Callable[..., Any], reply: Callable[..., bytes], tmp_path: Path
) -> None:
    """A named pipe is accepted as a source."""
    fifo = tmp_path / "reply.fifo"
    os.mkfifo(fifo)
    pid = os.fork()
    if pid == 0:  # the writer: feed the pipe, then leave without cleanup
        with open(fifo, "wb") as handle:
            handle.write(reply(OPS))
        os._exit(0)  # pylint: disable=protected-access
    try:
        run = paste_cli("paste", "apply", str(fifo), "--yes")
    finally:
        os.waitpid(pid, 0)
    assert run.code == 0, run.err


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("dir", "the paste source is not a regular file or a pipe"),
        ("missing.md", "the paste source could not be read"),
    ],
)
def test_bad_sources_are_refused(
    paste_cli: Callable[..., Any], tmp_path: Path, source: str, message: str
) -> None:
    """Directories and missing paths are refused without echoing the path."""
    (tmp_path / "dir").mkdir()
    run = paste_cli("paste", "apply", str(tmp_path / source), "--yes")
    assert (run.code, run.err) == (1, f"error: PasteError: {message}\n")


@pytest.mark.usefixtures("project")
def test_oversized_and_non_utf8_stdin_are_refused(
    paste_cli: Callable[..., Any], reply: Callable[..., bytes]
) -> None:
    """The cap and the encoding are checked before any parsing."""
    big = reply(OPS) + b" " * MAX_BYTES
    run = paste_cli("paste", "apply", "-", "--yes", stdin=big)
    assert run.err == "error: PasteError: the paste is larger than 256 KiB\n"
    run = paste_cli("paste", "apply", "-", "--yes", stdin=b"\xff\xfe" + reply(OPS))
    assert run.err == "error: PasteError: the paste is not valid UTF-8\n"


def test_missing_source_is_a_usage_error(paste_cli: Callable[..., Any]) -> None:
    """Exit codes are unchanged: argparse errors are 2."""
    assert paste_cli("paste", "apply").code == 2


@pytest.mark.usefixtures("project")
def test_op_failure_exits_1_and_names_the_op(
    paste_cli: Callable[..., Any], reply: Callable[..., bytes]
) -> None:
    """A failing op refuses the block with its number, before any prompt."""
    ops = [*OPS[:2], {"op": "item_update", "key": "goal-9", "expected_version": 1,
                      "changes": {"state": "done"}}]  # fmt: skip
    run = paste_cli("paste", "apply", "-", "--yes", stdin=reply(ops))
    assert (run.code, run.out) == (1, "")
    assert run.err == (
        "error: PasteOpError: op 3 (item_update): NotFoundError: item 'goal-9' not found\n"
    )
