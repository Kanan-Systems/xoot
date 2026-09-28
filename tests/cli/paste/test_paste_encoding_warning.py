"""
`xoot paste apply` warns, after the plan, about titles and bodies that look
damaged by a clipboard code page. The section names op numbers, keys or refs
and fields, never the text; it never blocks the apply; --json lists the
warnings; the receipt is unchanged.
"""

import json
from collections.abc import Callable
from typing import Any

import pytest

from xoot.cli.render.paste import ENCODING_ADVICE, ENCODING_HEADING
from xoot.repositories.item import item_db
from xoot.store.store import Store

MARKER = "damage-secret-7f3a"
DAMAGED = f"verificaci?n {MARKER}"
OPS = [
    {"op": "session_start", "title": "Paste LV A"},
    {"op": "item_create", "ref": "g", "kind": "goal", "title": DAMAGED},
    {"op": "capture", "ref": "c", "title": "fine", "body": f"a?b {MARKER}"},
]


def _section(err: str) -> list[str]:
    lines = err.splitlines()
    start = lines.index(ENCODING_HEADING)
    return lines[start : start + 4]


@pytest.mark.usefixtures("project")
def test_section_names_fields_never_content(
    paste_cli: Callable[..., Any], reply: Callable[..., bytes]
) -> None:
    """The section follows SIDE EFFECTS and holds no stored text."""
    run = paste_cli("paste", "apply", "-", "--yes", stdin=reply(OPS))
    assert run.code == 0, run.err
    lines = run.err.splitlines()
    assert lines.index(ENCODING_HEADING) > lines.index("SIDE EFFECTS")
    section = _section(run.err)
    assert section == [
        ENCODING_HEADING,
        "  op 2 $g title",
        "  op 3 $c body",
        f"  {ENCODING_ADVICE}",
    ]
    assert not any(MARKER in line or "verificaci" in line for line in section)


@pytest.mark.usefixtures("project")
def test_apply_still_works_after_yes(
    paste_cli: Callable[..., Any], reply: Callable[..., bytes], store: Store
) -> None:
    """A y on the terminal applies the block as pasted; the receipt is as usual."""
    run = paste_cli("paste", "apply", "-", stdin=reply(OPS), answer="y")
    assert run.code == 0, run.err
    assert ENCODING_HEADING in run.err and "Apply? [y/N] " in run.err
    receipt = run.receipt()
    assert set(receipt) == {
        "xoot", "project", "session", "session_status", "refs", "items", "decisions"
    }  # fmt: skip
    with store.read() as conn:
        goal = item_db.get_by_key(conn, receipt["refs"]["g"])
    assert goal is not None and goal.title == DAMAGED


@pytest.mark.usefixtures("project")
def test_no_still_writes_nothing(
    paste_cli: Callable[..., Any],
    reply: Callable[..., bytes],
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """The warning does not change what a refusal does."""
    before = row_counts()
    run = paste_cli("paste", "apply", "-", stdin=reply(OPS), answer="n")
    assert run.code == 1 and ENCODING_HEADING in run.err
    assert row_counts() == before


@pytest.mark.usefixtures("project")
def test_json_lists_warnings(
    paste_cli: Callable[..., Any], reply: Callable[..., bytes]
) -> None:
    """--json carries the warnings, still without any stored text."""
    run = paste_cli("paste", "apply", "-", "--yes", "--json", stdin=reply(OPS))
    result = json.loads(run.out)
    assert result["warnings"] == [
        {"index": 2, "target": "$g", "field": "title"},
        {"index": 3, "target": "$c", "field": "body"},
    ]
    assert MARKER not in run.out


@pytest.mark.usefixtures("project")
def test_clean_block_has_no_section(
    paste_cli: Callable[..., Any], reply: Callable[..., bytes]
) -> None:
    """Without damage there is no section, and --json shows an empty list."""
    ops = [{"op": "session_start", "title": "Why? verificación"}]
    run = paste_cli("paste", "apply", "-", "--yes", "--json", stdin=reply(ops))
    assert ENCODING_HEADING not in run.err
    assert json.loads(run.out)["warnings"] == []
