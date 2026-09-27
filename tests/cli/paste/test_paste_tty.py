"""
Confirmation on a real controlling terminal: the payload arrives on stdin
while the answer is typed on the pseudo-terminal the process controls.
Without a terminal and without --yes nothing is written.
"""

from collections.abc import Callable
from typing import Any

import pytest

from xoot.models.project.project import Project

OPS = [
    {"op": "session_start", "title": "plan"},
    {"op": "item_create", "ref": "g", "kind": "goal", "title": "goal"},
]


@pytest.mark.usefixtures("project")
def test_payload_on_stdin_and_yes_on_the_tty_applies(
    spawn: Callable[..., Any],
    reply: Callable[..., bytes],
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """The answer comes from /dev/tty, so stdin can carry the paste."""
    before = row_counts()
    run = spawn("paste", "apply", "-", stdin=reply(OPS), answer="y")
    assert run.code == 0, run.err
    assert "op 2 item_create: xoot-1 (new, $g)" in run.err
    assert "Apply? [y/N] " in run.err
    assert run.receipt()["refs"] == {"g": "xoot-1"}
    assert row_counts() != before


@pytest.mark.usefixtures("project")
def test_no_on_the_tty_writes_nothing(
    spawn: Callable[..., Any],
    reply: Callable[..., bytes],
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """Anything but y aborts after the plan was shown."""
    before = row_counts()
    run = spawn("paste", "apply", "-", stdin=reply(OPS), answer="n")
    assert (run.code, run.out) == (1, "")
    assert "paste plan: project xoot" in run.err
    assert run.err.endswith("error: ConfirmationError: aborted; nothing was written\n")
    assert row_counts() == before


@pytest.mark.usefixtures("project")
def test_no_terminal_and_no_yes_is_refused(
    spawn: Callable[..., Any],
    reply: Callable[..., bytes],
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """A new session with no controlling terminal cannot be asked."""
    before = row_counts()
    run = spawn("paste", "apply", "-", stdin=reply(OPS), answer=None)
    assert (run.code, run.out) == (1, "")
    assert run.err.endswith(
        "error: ConfirmationError: no controlling terminal to confirm on; "
        "pass --yes to confirm\n"
    )
    assert row_counts() == before


def test_yes_without_a_terminal_applies_and_prints_the_plan(
    project: Project,
    spawn: Callable[..., Any],
    reply: Callable[..., bytes],
) -> None:
    """--yes skips the question, never the plan."""
    run = spawn("paste", "apply", "-", "--yes", stdin=reply(OPS), answer=None)
    assert run.code == 0, run.err
    assert run.err.startswith(
        f"paste plan: project {project.key_prefix}, session xoot-S1"
    )
    assert "Apply?" not in run.err
    assert run.receipt()["session"] == "xoot-S1"
