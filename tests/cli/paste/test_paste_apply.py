"""
`xoot paste apply`: the source is read within the cap, the plan goes to
stderr with a SIDE EFFECTS section, and after confirmation stdout gets a
xoot-receipt block that maps refs to keys and never holds titles or bodies.
"""

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from xoot.repositories.item import item_db
from xoot.services.paste.parser import MAX_BYTES
from xoot.store.store import Store

MARKER = "receipt-secret-0b9e"
OPS = [
    {"op": "session_start", "title": f"s {MARKER}"},
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
        "paste plan: project xoot, session xoot-S1 (open after the block)",
        "  op 1 session_start: xoot-S1 (new)",
        "  op 2 item_create: xoot-1 (new, $g)",
        "  op 3 item_create: xoot-2 (new, $b)",
        "  op 4 item_update: xoot-2",
        "      xoot-2 state: open -> active",
        "  op 5 decision_record: xoot-D1 (new, $d)",
        "SIDE EFFECTS",
        "  (none)",
    ]
    assert run.out.startswith("```xoot-receipt\n")


@pytest.mark.usefixtures("project")
def test_receipt_maps_refs_and_holds_no_text(
    paste_cli: Callable[..., Any], reply: Callable[..., bytes], store: Store
) -> None:
    """The receipt parses, its keys are real, and no title or body leaks."""
    run = paste_cli("paste", "apply", "-", "--yes", stdin=reply(OPS))
    receipt = run.receipt()
    assert receipt == {
        "xoot": 1,
        "project": "xoot",
        "session": "xoot-S1",
        "session_status": "open",
        "refs": {"g": "xoot-1", "b": "xoot-2", "d": "xoot-D1"},
        "items": [
            {"key": "xoot-1", "version": 1, "state": "open"},
            {"key": "xoot-2", "version": 2, "state": "active"},
        ],
        "decisions": [{"key": "xoot-D1", "version": 1, "status": "locked"}],
    }
    with store.read() as conn:
        batch = item_db.get_by_key(conn, receipt["refs"]["b"])
    assert batch is not None and batch.version == 2
    assert MARKER not in run.out and MARKER not in run.err


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
    assert [o["op"] for o in result["outcomes"]][:2] == ["session_start", "item_create"]
    assert result["refs"]["g"] == "xoot-1" and result["auto_backlog"] == []
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


@pytest.mark.usefixtures("project")
def test_side_effects_list_the_auto_backlog_moves(
    paste_cli: Callable[..., Any], reply: Callable[..., bytes]
) -> None:
    """A close that retires an earlier session's backlog says so separately."""
    park = [
        {"op": "session_start", "title": "first"},
        {"op": "item_create", "ref": "t", "kind": "subtask", "title": "t"},
        {"op": "session_close", "dispositions": {"$t": "session_backlog"}},
    ]
    assert paste_cli("paste", "apply", "-", "--yes", stdin=reply(park)).code == 0
    ops = [
        {"op": "session_start", "title": "next"},
        {"op": "session_close", "dispositions": {}},
    ]
    run = paste_cli("paste", "apply", "-", "--yes", stdin=reply(ops))
    assert run.code == 0, run.err
    lines = run.err.splitlines()
    effects = lines[lines.index("SIDE EFFECTS") + 1 :]
    assert effects == [
        "  xoot-1: moves from the backlog of xoot-S1 to the project backlog"
    ]


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
    ops = [*OPS[:2], {"op": "item_update", "key": "xoot-9", "expected_version": 1,
                      "changes": {"state": "done"}}]  # fmt: skip
    run = paste_cli("paste", "apply", "-", "--yes", stdin=reply(ops))
    assert (run.code, run.out) == (1, "")
    assert run.err == (
        "error: PasteOpError: op 3 (item_update): NotFoundError: item 'xoot-9' not found\n"
    )
