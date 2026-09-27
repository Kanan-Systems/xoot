"""Every command succeeds in text and in --json, and JSON output parses."""

from pathlib import Path
from typing import Any

import pytest

from xoot.models.item.item import Item

CASES: dict[str, list[str]] = {
    "init": ["init", "{tmp}/newp", "--prefix", "newp", "--alias", "np"],
    "project list": ["project", "list"],
    "project show": ["project", "show", "--project", "xo"],
    "add-alias": ["project", "add-alias", "xa", "--project", "xoot"],
    "remove-alias": ["project", "remove-alias", "xo", "--project", "xoot", "--yes"],
    "add-path": ["project", "add-path", "{tmp}/extra", "--project", "xo"],
    "remove-path": ["project", "remove-path", "/work/xoot", "--project", "xo", "--yes"],
    "brief": ["brief", "--project", "xo"],
    "tree": ["tree", "--project", "xo", "--all"],
    "workflow export": ["workflow", "export", "--project", "xo"],
    "workflow export -o": [
        "workflow",
        "export",
        "--project",
        "xo",
        "-o",
        "{tmp}/o.toml",
    ],
    "workflow import": ["workflow", "import", "{toml}", "--project", "xo", "--yes"],
    "redact": ["redact", "xoot-1", "title", "--yes"],
    "db stats": ["db", "stats"],
    "db vacuum": ["db", "vacuum"],
}


def _argv(case: str, tmp_path: Path, toml: Path) -> list[str]:
    return [
        part.format(tmp=tmp_path, toml=toml) if "{" in part else part
        for part in CASES[case]
    ]


@pytest.mark.usefixtures("secret_item")
@pytest.mark.parametrize("json_mode", [False, True], ids=["text", "json"])
@pytest.mark.parametrize("case", list(CASES))
def test_happy_path(
    xoot: Any, tmp_path: Path, default_toml: Path, case: str, json_mode: bool
) -> None:
    """Exit 0, a result on stdout, nothing on stderr; --json parses."""
    argv = _argv(case, tmp_path, default_toml) + (["--json"] if json_mode else [])
    run = xoot(*argv)
    assert (run.code, run.err) == (0, ""), run.err
    assert run.out.strip()
    if json_mode:
        assert isinstance(run.json(), dict)


def test_results_say_what_happened(
    xoot: Any, tmp_path: Path, secret_item: Item, marker: str
) -> None:
    """Spot checks of the text and JSON content of several commands."""
    init = xoot("init", str(tmp_path / "newp"), "--prefix", "newp", "--json").json()
    assert init == {
        "key_prefix": "newp",
        "name": "newp",
        "aliases": [],
        "paths": [str(tmp_path / "newp")],
    }
    listing = xoot("project", "list").out.splitlines()
    assert listing[1].split() == ["PREFIX", "NAME", "ALIASES", "PATHS"]
    assert listing[3].split() == ["xoot", "xoot", "xo", "/work/xoot"]
    tree = xoot("tree", "--project", "xoot").out
    assert tree == f"xoot-1  goal  open (open)  t {marker}\n"
    assert "Counts\n  open: 1" in xoot("brief", "--project", "xo").out
    exported = xoot("workflow", "export", "--project", "xo", "-o", str(tmp_path / "w"))
    assert exported.out == f"wrote xoot workflow version 1 to {tmp_path / 'w'}\n"
    redacted = xoot("redact", secret_item.key, "body", "--yes", "--json").json()
    assert (redacted["field"], redacted["version"], redacted["purged"]) == (
        "body",
        2,
        True,
    )
