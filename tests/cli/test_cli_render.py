"""
Text layout: tree columns line up at every depth, brief tables start with a
header row, and the brief caps its open sessions and says when it did.
"""

import re
from collections.abc import Callable
from typing import Any

from xoot.models.event.actor import Actor
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.models.session.session_start import SessionStart
from xoot.server.brief import LIST_MAX
from xoot.services.item_service import update_item
from xoot.services.session_service import start_session
from xoot.store.store import Store

# Indented key, kind, "state (category)", title: each column after the first
# is found by where its text starts.
_TREE_LINE = re.compile(r"^(\s*\S+)\s+(\S+)\s+(\S+ \(\S+\))\s+(.+)$")


def _section(out: str, title: str) -> list[str]:
    """The lines of one brief section, title excluded."""
    block = next(part for part in out.split("\n\n") if part.startswith(title + "\n"))
    return block.splitlines()[1:]


def _starts(line: str, cells: tuple[str, ...]) -> tuple[int, ...]:
    """Where each cell starts in a table line, scanning left to right."""
    offsets, cursor = [], 0
    for cell in cells:
        cursor = line.index(cell, cursor)
        offsets.append(cursor)
        cursor += len(cell)
    return tuple(offsets)


def test_tree_columns_are_aligned(
    xoot: Any,
    store: Store,
    project: Project,
    ctx: WriteContext,
    make_item: Callable[..., Item],
) -> None:
    """Kind, state and title start at one column on every line, at any depth."""
    goal = make_item(project, ItemKind.GOAL, title="first goal")
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id, title="a batch")
    make_item(project, ItemKind.SUBTASK, parent_id=batch.id, title="deep task")
    other = make_item(project, ItemKind.GOAL, title="second goal")
    update_item(store, other.id, 1, ItemUpdate(state="awaiting_input"), ctx)

    run = xoot("tree", "--project", "xo", "--all")
    assert run.code == 0, run.err
    lines = run.out.splitlines()
    matches = [_TREE_LINE.match(line) for line in lines]
    assert all(matches) and len(lines) == 4
    starts = {tuple(m.start(g) for g in (2, 3, 4)) for m in matches if m}
    assert len(starts) == 1
    assert lines[2].startswith("    xoot-3  subtask")


def test_brief_tables_have_a_header_row(
    xoot: Any, store: Store, project: Project, user: Actor
) -> None:
    """Every row, the first included, is data under a header of column names."""
    for title in ("short", "a much longer session title"):
        start_session(store, project.id, SessionStart(title=title), user)

    run = xoot("brief", "--project", "xo")
    assert run.code == 0, run.err
    header, *rows = _section(run.out, "Open sessions")
    assert header.split() == ["key", "title", "client", "started"]
    assert [row.split()[0] for row in rows] == ["xoot-S1", "xoot-S2"]
    columns = {_starts(header, ("key", "title", "client", "started"))}
    for row, title in zip(rows, ("short", "a much longer session title")):
        key, _, rest = row.strip().partition("  ")
        client, started = rest[len(title) :].split()
        columns.add(_starts(row, (key, title, client, started)))
    assert len(columns) == 1
    assert "(first" not in run.out


def test_brief_caps_open_sessions(
    xoot: Any, make_session: Callable[..., Session], project: Project
) -> None:
    """Past the cap, the brief lists the first ones and flags the rest."""
    for _ in range(LIST_MAX + 1):
        make_session(project)

    brief = xoot("brief", "--project", "xo", "--json").json()
    assert len(brief["open_sessions"]) == LIST_MAX
    assert brief["open_sessions"][-1]["key"] == f"xoot-S{LIST_MAX}"
    assert brief["open_sessions_truncated"] is True
    text = xoot("brief", "--project", "xo").out
    assert len(_section(text, "Open sessions")) == LIST_MAX + 2
    assert f"  (first {LIST_MAX} shown; more are open)" in text


def test_brief_at_the_cap_is_not_truncated(
    xoot: Any, make_session: Callable[..., Session], project: Project
) -> None:
    """Exactly the cap fits, so nothing is flagged."""
    for _ in range(LIST_MAX):
        make_session(project)

    brief = xoot("brief", "--project", "xo", "--json").json()
    assert len(brief["open_sessions"]) == LIST_MAX
    assert brief["open_sessions_truncated"] is False
