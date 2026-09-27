"""T1: every command has working --help; malformed usage exits 2."""

from pathlib import Path
from typing import Any

import pytest

COMMANDS = [
    [],
    ["init"],
    ["project"],
    ["project", "list"],
    ["project", "show"],
    ["project", "add-alias"],
    ["project", "remove-alias"],
    ["project", "add-path"],
    ["project", "remove-path"],
    ["brief"],
    ["tree"],
    ["workflow"],
    ["workflow", "export"],
    ["workflow", "import"],
    ["redact"],
    ["db"],
    ["db", "stats"],
    ["db", "vacuum"],
]


@pytest.mark.parametrize("command", COMMANDS, ids=lambda c: " ".join(c) or "xoot")
def test_help(xoot: Any, db_path: Path, command: list[str]) -> None:
    """--help prints usage to stdout, exits 0 and opens no database."""
    run = xoot(*command, "--help")
    assert run.code == 0
    assert run.out.startswith("usage: xoot") and run.err == ""
    assert not db_path.exists()


@pytest.mark.parametrize(
    "argv",
    [
        ["frobnicate"],
        [],
        ["project"],
        ["project", "rename"],
        ["init"],
        ["tree", "--depth", "9"],
        ["tree", "--depth", "x"],
        ["workflow", "import", "f.toml", "--map", "goal-open"],
        ["redact", "xoot-1", "state"],
        ["brief", "--bogus"],
    ],
    ids=lambda a: " ".join(a) or "no command",
)
def test_usage_errors_exit_2(xoot: Any, db_path: Path, argv: list[str]) -> None:
    """argparse refuses unknown or malformed usage on stderr, before any open."""
    run = xoot(*argv)
    assert run.code == 2
    assert run.out == "" and "usage: xoot" in run.err
    assert not db_path.exists()


def test_global_options_before_or_after_the_command(xoot: Any) -> None:
    """--json works in either position."""
    assert xoot("--json", "project", "list").json()["projects"] == []
    assert xoot("project", "list", "--json").json()["projects"] == []
