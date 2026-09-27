"""
Plan digests cover every column an apply writes, not only keys and states.

Each plan type is previewed twice with one difference that leaves every
state alone: a backlog target or a parent. The digests must differ.
"""

from collections.abc import Callable

import pytest

from xoot.models.confirm.plan_entry import PlanEntry
from xoot.models.event.write_context import WriteContext
from xoot.models.item.bulk_create import BulkCreate
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.session.disposition import Disposition
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.services.bulk_service import preview_bulk
from xoot.services.confirm_service import plan_digest
from xoot.services.item_service import update_item
from xoot.services.session_close_service import preview_close
from xoot.services.subtree_service import apply_reparent, preview_drop, preview_reparent
from xoot.store.store import Store

ENTRY = PlanEntry(
    key="xoot-1",
    kind=ItemKind.SUBTASK,
    title="t",
    body_sha256="0" * 64,
    state="backlogged",
    parent_key=None,
    backlog_session_key="xoot-S1",
    awaiting_decision_key=None,
)


def test_digest_ignores_entry_order() -> None:
    """The same entries in another order give the same digest."""
    other = ENTRY.model_copy(update={"key": "xoot-2"})
    assert plan_digest([ENTRY, other]) == plan_digest([other, ENTRY])


@pytest.mark.parametrize(
    "field, value",
    [
        ("key", "xoot-2"),
        ("kind", ItemKind.BATCH),
        ("title", "u"),
        ("body_sha256", "1" * 64),
        ("state", "dropped"),
        ("parent_key", "xoot-9"),
        ("backlog_session_key", None),
        ("awaiting_decision_key", "xoot-D1"),
        ("disposition", Disposition.SESSION_BACKLOG),
    ],
)
def test_digest_changes_with_every_field(field: str, value: object) -> None:
    """Changing any one column of one entry changes the digest."""
    assert plan_digest([ENTRY]) != plan_digest(
        [ENTRY.model_copy(update={field: value})]
    )


def test_bulk_digest_pins_the_parent(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
) -> None:
    """The same new batch under two different goals plans two digests."""
    first = make_item(project, ItemKind.GOAL)
    second = make_item(project, ItemKind.GOAL)
    session = make_session(project)

    def digest(parent: Item) -> str:
        request = BulkCreate.model_validate(
            {"items": [{"kind": "batch", "title": "b", "parent_id": parent.id}]}
        )
        return preview_bulk(store, session.id, request).plan_sha256

    assert digest(first) != digest(second)


def test_drop_digest_pins_the_parent(
    store: Store,
    project: Project,
    ctx: WriteContext,
    make_item: Callable[..., Item],
) -> None:
    """Dropping the same batch after it moved to another goal plans a new digest."""
    first = make_item(project, ItemKind.GOAL)
    second = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=first.id)
    before = preview_drop(store, batch.id).plan_sha256
    apply_reparent(store, batch.id, second.id, batch.version, ctx)
    assert preview_drop(store, batch.id).plan_sha256 != before


def test_reparent_digest_pins_the_new_parent(
    store: Store, project: Project, make_item: Callable[..., Item]
) -> None:
    """Moving the same batch under two different goals plans two digests."""
    home = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=home.id)
    first = make_item(project, ItemKind.GOAL)
    second = make_item(project, ItemKind.GOAL)
    assert (
        preview_reparent(store, batch.id, first.id).plan_sha256
        != preview_reparent(store, batch.id, second.id).plan_sha256
    )


def test_close_digest_pins_the_backlog_target(
    store: Store,
    ctx: WriteContext,
    carried_backlog: tuple[Item, Session, SessionClose],
) -> None:
    """A carried-over backlogged item moved to the project backlog plans a new digest."""
    item, session, request = carried_backlog
    before = preview_close(store, session.id, request).plan_sha256
    update_item(store, item.id, item.version, ItemUpdate(backlog_session_id=None), ctx)
    assert preview_close(store, session.id, request).plan_sha256 != before


def test_close_digest_tells_session_from_project_backlog(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
) -> None:
    """Both backlog dispositions end in the backlogged state, yet digest apart."""
    item = make_item(project, ItemKind.SUBTASK)
    session = make_session(project, item.id)

    def digest(disposition: Disposition) -> str:
        request = SessionClose(dispositions={item.id: disposition})
        return preview_close(store, session.id, request).plan_sha256

    assert digest(Disposition.SESSION_BACKLOG) != digest(Disposition.PROJECT_BACKLOG)
