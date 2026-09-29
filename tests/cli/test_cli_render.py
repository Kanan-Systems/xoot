"""
Text layout: tree columns line up at every depth, brief tables start with a
header row, and the brief caps its open goals and says when it did.
"""

import re
from collections.abc import Callable
from typing import Any

from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.server.brief import LIST_MAX
from xoot.services.item_service import update_item
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
    assert lines[2].startswith("    goal-1/batch-1/subtask-1  subtask")


def test_brief_tables_have_a_header_row(
    xoot: Any, project: Project, make_item: Callable[..., Item]
) -> None:
    """Every row, the first included, is data under a header of column names."""
    for title in ("short", "a much longer goal title"):
        make_item(project, ItemKind.GOAL, title=title)

    run = xoot("brief", "--project", "xo")
    assert run.code == 0, run.err
    header, *rows = _section(run.out, "Open goals")
    assert header.split() == ["key", "state", "batches", "backlog", "title"]
    assert [row.split()[0] for row in rows] == ["goal-1", "goal-2"]
    columns = {_starts(header, ("key", "state", "batches", "backlog", "title"))}
    for row, title in zip(rows, ("short", "a much longer goal title")):
        key = row.split()[0]
        columns.add(_starts(row, (key, "open", "0 of 0 done", "0", title)))
    assert len(columns) == 1
    assert "(first" not in run.out


def test_brief_caps_open_goals(
    xoot: Any, make_item: Callable[..., Item], project: Project
) -> None:
    """Past the cap, the brief lists the first ones and flags the rest."""
    for _ in range(LIST_MAX + 1):
        make_item(project, ItemKind.GOAL)

    brief = xoot("brief", "--project", "xo", "--json").json()
    assert len(brief["open_goals"]) == LIST_MAX
    assert brief["open_goals"][-1]["key"] == f"goal-{LIST_MAX}"
    assert brief["open_goals_truncated"] is True
    text = xoot("brief", "--project", "xo").out
    assert len(_section(text, "Open goals")) == LIST_MAX + 2
    assert f"  (first {LIST_MAX} shown; more are open)" in text


def test_brief_at_the_cap_is_not_truncated(
    xoot: Any, make_item: Callable[..., Item], project: Project
) -> None:
    """Exactly the cap fits, so nothing is flagged."""
    for _ in range(LIST_MAX):
        make_item(project, ItemKind.GOAL)

    brief = xoot("brief", "--project", "xo", "--json").json()
    assert len(brief["open_goals"]) == LIST_MAX
    assert brief["open_goals_truncated"] is False


def test_brief_shows_blocked_and_backlog_levels(
    xoot: Any,
    work_tree: tuple[Item, Item, Item, Item],
    capture_on: Callable[..., Item],
    set_state: Callable[..., Item],
) -> None:
    """The text brief names what backlog blocks and counts each level."""
    _, _, first, second = work_tree
    capture_on(first)
    set_state(first, "done")
    set_state(second, "done")
    text = xoot("brief", "--project", "xo").out
    assert _section(text, "Blocked by open backlog")[1].split() == [
        "goal-1/batch-1",
        "1",
    ]
    assert "project: 0  goal: 0  batch: 1" in text
