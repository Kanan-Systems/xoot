"""W2, W3: session_close refuses missing dispositions and warns of auto-backlog moves."""

from collections.abc import Callable
from typing import Any

from mcp import ClientSession

from xoot.models.event.actor import Actor
from xoot.models.item.item import Item
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.session.disposition import Disposition
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.services.item_service import capture
from xoot.services.session_close_service import close_session
from xoot.store.store import Store


def test_missing_dispositions_are_refused_without_writing(
    project: Project,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
    row_counts: Callable[[], dict[str, int]],
    harness: Any,
) -> None:
    """No preview, no token, no row of any table: only the missing keys."""
    first = make_item(project, ItemKind.GOAL)
    second = make_item(project, ItemKind.GOAL)
    third = make_item(project, ItemKind.GOAL)
    session = make_session(project, first.id, second.id, third.id)
    before = row_counts()

    async def scenario(client: ClientSession) -> str:
        return await harness.error(
            client,
            "session_close",
            session=f"xoot-S{session.number}",
            dispositions={second.key: "carry_over"},
        )

    message = harness.run(scenario)
    assert message == (
        "Error executing tool session_close: "
        f"missing dispositions: {first.key}, {third.key}"
    )
    after = row_counts()
    assert after == before
    assert after["confirm_token"] == 0


def test_preview_warns_of_every_auto_backlog_move(
    store: Store,
    project: Project,
    user: Actor,
    make_session: Callable[..., Session],
    harness: Any,
) -> None:
    """Stale session-backlog items appear as warnings naming origin and target."""
    early = make_session(project)
    stale = [
        capture(store, early.id, ItemDraft(title=title), user)
        for title in ("stale one", "stale two")
    ]
    close_session(
        store,
        early.id,
        SessionClose(
            dispositions={item.id: Disposition.SESSION_BACKLOG for item in stale}
        ),
        user,
    )
    current = make_session(project)

    async def scenario(client: ClientSession) -> dict[str, Any]:
        return await harness.ok(
            client,
            "session_close",
            session=f"xoot-S{current.number}",
            dispositions={},
        )

    out = harness.run(scenario)
    assert out["confirm_token"]
    warnings = out["preview"]["warnings"]
    assert warnings == [
        {
            "kind": "auto_backlog",
            "key": item.key,
            "origin_session": f"xoot-S{early.number}",
            "target": "project_backlog",
        }
        for item in stale
    ]
    assert [entry["key"] for entry in out["preview"]["auto_backlog"]] == [
        item.key for item in stale
    ]
