"""
X4: item and decision create events store a body digest, not the body;
update events keep the changed fields, body included.
"""

import hashlib

import pytest

from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.event.entity_type import EntityType
from xoot.models.event.event import Event
from xoot.models.event.event_action import EventAction
from xoot.models.event.write_context import WriteContext
from xoot.models.fields import BODY_MAX
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.repositories.event import event_db
from xoot.services.decision_service import create_decision
from xoot.services.item_service import create_item, update_item
from xoot.store.store import Store

BIG_BODY = "b" * BODY_MAX


def _events(store: Store, entity_type: EntityType, entity_id: int) -> list[Event]:
    with store.read() as conn:
        return event_db.list_for_entity(conn, entity_type, entity_id)


def _stored_bytes(store: Store, event_id: int, column: str) -> int:
    with store.read() as conn:
        # column is one of two literals from this module, never input.
        row = conn.execute(
            f"SELECT length(CAST({column} AS BLOB)) FROM event WHERE id = ?",
            (event_id,),
        ).fetchone()
    return int(row[0])


@pytest.mark.parametrize("entity_type", [EntityType.ITEM, EntityType.DECISION])
def test_create_event_stores_digest_not_body(
    store: Store, project: Project, ctx: WriteContext, entity_type: EntityType
) -> None:
    """A 32768-character body leaves a create event under 1 KB."""
    if entity_type is EntityType.ITEM:
        request = ItemCreate(kind=ItemKind.GOAL, title="big", body=BIG_BODY)
        entity_id = create_item(store, project.id, request, ctx).id
    else:
        decision = DecisionCreate(title="big", body=BIG_BODY)
        entity_id = create_decision(store, project.id, decision, ctx).id
    (created,) = _events(store, entity_type, entity_id)
    assert created.action is EventAction.CREATE
    assert created.after is not None
    assert "body" not in created.after
    assert created.after["body_sha256"] == hashlib.sha256(BIG_BODY.encode()).hexdigest()
    assert created.after["body_len"] == BODY_MAX
    assert _stored_bytes(store, created.id, "after") < 1024


def test_update_events_keep_changed_fields(
    store: Store, project: Project, ctx: WriteContext
) -> None:
    """A body update's before holds the original body; title updates omit it."""
    item = create_item(
        store, project.id, ItemCreate(kind=ItemKind.GOAL, title="t", body=BIG_BODY), ctx
    )
    item = update_item(store, item.id, 1, ItemUpdate(title="t2"), ctx)
    update_item(store, item.id, 2, ItemUpdate(body="short"), ctx)
    _, title_change, body_change = _events(store, EntityType.ITEM, item.id)
    assert (title_change.before, title_change.after) == (
        {"title": "t", "version": 1},
        {"title": "t2", "version": 2},
    )
    assert (body_change.before, body_change.after) == (
        {"body": BIG_BODY, "version": 2},
        {"body": "short", "version": 3},
    )
