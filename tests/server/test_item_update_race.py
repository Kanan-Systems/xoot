"""
item_update picks its path from a read snapshot; a path that skips the
preview re-checks for children under the write lock, and refuses, writing
nothing, when a child appeared in between.
"""

from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.server.schemas.item_changes_input import ItemChangesInput
from xoot.server.tools import item_update_tool
from xoot.services.item_service import get_item
from xoot.store.store import Store


@pytest.fixture(name="call_racing")
def fixture_call_racing(
    monkeypatch: pytest.MonkeyPatch,
    db_path: Path,
    row_counts: Callable[[], dict[str, int]],
    project: Project,
    make_session: Callable[..., Session],
) -> Callable[..., dict[str, int]]:
    """
    Factory: open session xoot-S1, then call item_update in it with an
    interleaved write between the path decision and the apply; return the
    row counts right after that write.

    The tool's database work runs inline on this thread, so the interleaved
    write can use the test's own store while the tool holds its snapshot.
    """

    async def inline(_ctx: Any, work: Callable[[Store], Any]) -> Any:
        with Store.open(db_path) as store:
            return work(store)

    monkeypatch.setattr(item_update_tool, "run_db", inline)

    def call(
        interleave: Callable[[], object], key: str, **changes: Any
    ) -> dict[str, int]:
        # The hook point is the private path decision; there is no public seam.
        decide = item_update_tool._request  # pylint: disable=protected-access
        make_session(project)
        counts: dict[str, int] = {}

        def racing(*args: Any) -> Any:
            chosen = decide(*args)
            interleave()
            counts.update(row_counts())
            return chosen

        monkeypatch.setattr(item_update_tool, "_request", racing)
        tool: Callable[[], Awaitable[Any]] = partial(
            item_update_tool.item_update,
            None,
            session="xoot-S1",
            key=key,
            expected_version=1,
            changes=ItemChangesInput(**changes),
        )
        with pytest.raises(
            ToolError, match="^preview required: the item now has children$"
        ):
            anyio.run(tool)
        return counts

    return call


def test_direct_drop_is_refused_when_a_child_appears(
    project: Project,
    store: Store,
    make_item: Callable[..., Item],
    row_counts: Callable[[], dict[str, int]],
    call_racing: Callable[..., dict[str, int]],
) -> None:
    """A childless goal's drop skips the preview; a new child forces one."""
    goal = make_item(project, ItemKind.GOAL)

    counts = call_racing(
        lambda: make_item(project, ItemKind.BATCH, parent_id=goal.id),
        goal.key,
        state="dropped",
    )

    assert row_counts() == counts
    after = get_item(store, goal.id)
    assert (after.state, after.version) == (goal.state, 1)


def test_direct_reparent_is_refused_when_a_child_appears(
    project: Project,
    store: Store,
    make_item: Callable[..., Item],
    row_counts: Callable[[], dict[str, int]],
    call_racing: Callable[..., dict[str, int]],
) -> None:
    """A childless batch moves without a preview; a new child forces one."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    other_goal = make_item(project, ItemKind.GOAL)

    counts = call_racing(
        lambda: make_item(project, ItemKind.SUBTASK, parent_id=batch.id),
        batch.key,
        parent=other_goal.key,
    )

    assert row_counts() == counts
    after = get_item(store, batch.id)
    assert (after.parent_id, after.version) == (goal.id, 1)
