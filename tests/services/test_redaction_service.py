"""
X5/Y1/Y4: user-only redaction of item and decision titles and bodies,
session titles and summaries and project names, in the row and in every
event of the entity. On-disk bytes are covered in test_redaction_disk.
"""

from collections.abc import Callable

import pytest

from xoot.exceptions.not_found_error import NotFoundError
from xoot.exceptions.redaction_error import RedactionError
from xoot.exceptions.version_conflict_error import VersionConflictError
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.decision.decision_update import DecisionUpdate
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.entity_type import EntityType
from xoot.models.event.event import Event
from xoot.models.event.event_action import EventAction
from xoot.models.event.redactable_field import RedactableField
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.session.client import Client
from xoot.models.session.session_close import SessionClose
from xoot.models.session.session_start import SessionStart
from xoot.repositories.event import event_db
from xoot.services import redaction_service
from xoot.services.decision_service import (
    create_decision,
    get_decision,
    update_decision,
)
from xoot.services.item_service import create_item, get_item, update_item
from xoot.services.project_service import get_project
from xoot.services.redaction_service import REDACTED, redact_field
from xoot.services.session_close_service import close_session
from xoot.services.session_service import get_session, start_session
from xoot.store.store import Store

TARGETS = [
    ("item", "title"),
    ("item", "body"),
    ("decision", "title"),
    ("decision", "body"),
    ("session", "title"),
    ("session", "summary"),
    ("project", "name"),
]


def _events(store: Store, entity_type: EntityType, entity_id: int) -> list[Event]:
    with store.read() as conn:
        return event_db.list_for_entity(conn, entity_type, entity_id)


def _rows(store: Store, project: Project, ctx: WriteContext) -> dict[str, int]:
    """One row of every redactable entity, each with every field filled."""
    item = ItemCreate(kind=ItemKind.GOAL, title="t", body="b")
    session = start_session(store, project.id, SessionStart(title="s"), ctx.actor)
    close_session(store, session.session.id, SessionClose(summary="sum"), ctx.actor)
    return {
        "item": create_item(store, project.id, item, ctx).id,
        "decision": create_decision(
            store, project.id, DecisionCreate(title="d", body="b"), ctx
        ).id,
        "session": session.session.id,
        "project": project.id,
    }


def test_item_body_is_redacted_in_row_and_history(
    store: Store, project: Project, user: Actor, ctx: WriteContext
) -> None:
    """Row, create digest and body-update values are scrubbed; others untouched."""
    item = create_item(
        store, project.id, ItemCreate(kind=ItemKind.GOAL, title="t", body="one"), ctx
    )
    update_item(store, item.id, 1, ItemUpdate(body="two"), ctx)
    update_item(store, item.id, 2, ItemUpdate(title="t2"), ctx)
    result = redact_field(store, EntityType.ITEM, item.id, RedactableField.BODY, user)
    assert (get_item(store, item.id).body, get_item(store, item.id).version) == (
        REDACTED,
        4,
    )
    created, body_change, title_change, redact = _events(
        store, EntityType.ITEM, item.id
    )
    assert created.after is not None
    assert (created.after["body_sha256"], created.after["body_len"]) == (None, None)
    assert (body_change.before, body_change.after) == (
        {"body": REDACTED, "version": 1},
        {"body": REDACTED, "version": 2},
    )
    assert title_change.after == {"title": "t2", "version": 3}
    assert title_change.redacted_at is None
    assert created.redacted_at is not None and body_change.redacted_at is not None
    assert (redact.action, redact.before, redact.after) == (
        EventAction.REDACT,
        {"version": 3},
        {"field": "body", "version": 4},
    )
    assert (redact.actor_kind, redact.client) == (ActorKind.USER, Client.CLI)
    assert result.redacted_event_ids == (created.id, body_change.id)
    assert (result.version, result.purged) == (4, True)


def test_decision_title_is_redacted(
    store: Store, project: Project, user: Actor, ctx: WriteContext
) -> None:
    """Decisions work the same; a title redaction keeps the body digest."""
    decision = create_decision(
        store, project.id, DecisionCreate(title="leak", body="b"), ctx
    )
    update_decision(store, decision.id, 1, DecisionUpdate(title="leak2"), ctx)
    redact_field(store, "decision", decision.id, "title", user)
    assert get_decision(store, decision.id).title == REDACTED
    created, renamed, _ = _events(store, EntityType.DECISION, decision.id)
    assert created.after is not None
    assert created.after["title"] == REDACTED
    assert created.after["body_len"] == 1
    assert (renamed.before, renamed.after) == (
        {"title": REDACTED, "version": 1},
        {"title": REDACTED, "version": 2},
    )


def test_session_summary_is_redacted(
    store: Store, project: Project, user: Actor
) -> None:
    """The close event's summary is scrubbed; the create's NULL stays NULL."""
    started = start_session(store, project.id, SessionStart(title="s"), user)
    session_id = started.session.id
    close_session(store, session_id, SessionClose(summary="private"), user)
    result = redact_field(store, "session", session_id, "summary", user)
    assert get_session(store, session_id).summary == REDACTED
    created, closed, redact = _events(store, EntityType.SESSION, session_id)
    assert created.after is not None and created.after["summary"] is None
    assert closed.after is not None and closed.after["summary"] == REDACTED
    assert (redact.before, redact.after) == (None, {"field": "summary"})
    assert result.version is None
    assert result.redacted_event_ids == (closed.id,)


def test_project_name_is_redacted(store: Store, project: Project, user: Actor) -> None:
    """The project row and its create snapshot lose the name."""
    redact_field(store, EntityType.PROJECT, project.id, "name", user)
    assert get_project(store, project.id).name == REDACTED
    created = _events(store, EntityType.PROJECT, project.id)[0]
    assert created.after is not None and created.after["name"] == REDACTED


def test_stale_write_after_redaction_names_the_redaction(
    store: Store, project: Project, user: Actor, claude: Actor
) -> None:
    """Y1: the conflict's changed field and actor come from the redact event."""
    ctx = WriteContext(actor=claude)
    item = create_item(
        store, project.id, ItemCreate(kind=ItemKind.GOAL, title="t", body="b"), ctx
    )
    redact_field(store, EntityType.ITEM, item.id, "body", user)
    with pytest.raises(VersionConflictError) as caught:
        update_item(store, item.id, 1, ItemUpdate(title="stale"), ctx)
    assert caught.value.current_version == 2
    assert caught.value.changed_fields == ("body",)
    assert caught.value.actors == (user,)


@pytest.mark.parametrize(
    "case",
    [
        (*target, kind)
        for target in TARGETS
        for kind in (ActorKind.CLAUDE, ActorKind.SYSTEM)
    ],
)
def test_non_user_actor_is_refused(
    store: Store,
    project: Project,
    ctx: WriteContext,
    row_counts: Callable[[], dict[str, int]],
    case: tuple[str, str, ActorKind],
) -> None:
    """Only the user may redact; the refusal writes nothing and runs no SQL."""
    entity, field, kind = case
    entity_id = _rows(store, project, ctx)[entity]
    before = row_counts()
    statements: list[str] = []
    store.conn.set_trace_callback(statements.append)
    try:
        with pytest.raises(RedactionError, match="only the user"):
            redact_field(
                store, entity, entity_id, field, Actor(kind=kind, client=Client.CODE)
            )
    finally:
        store.conn.set_trace_callback(None)
    assert not statements
    assert row_counts() == before


@pytest.mark.parametrize(
    ("entity", "field"),
    [
        ("project", "title"),
        ("session", "body"),
        ("item", "summary"),
        ("decision", "name"),
        ("workflow", "name"),
        ("nope", "body"),
        ("item", "state"),
    ],
)
def test_unsupported_target_is_refused(
    store: Store, project: Project, user: Actor, entity: str, field: str
) -> None:
    """Only the listed entity/field pairs can be redacted."""
    with pytest.raises(RedactionError, match="cannot redact"):
        redact_field(store, entity, project.id, field, user)


@pytest.mark.parametrize(
    "target", ["open-session-summary", "item-body", "decision-body"]
)
def test_null_or_empty_field_is_refused(
    store: Store,
    project: Project,
    ctx: WriteContext,
    row_counts: Callable[[], dict[str, int]],
    target: str,
) -> None:
    """A NULL summary or an empty body has nothing to redact; nothing is written."""
    if target == "open-session-summary":
        request = SessionStart(title="s")
        entity_id = start_session(store, project.id, request, ctx.actor).session.id
        entity, field = "session", "summary"
    elif target == "item-body":
        request = ItemCreate(kind=ItemKind.GOAL, title="t")
        entity_id = create_item(store, project.id, request, ctx).id
        entity, field = "item", "body"
    else:
        request = DecisionCreate(title="d")
        entity_id = create_decision(store, project.id, request, ctx).id
        entity, field = "decision", "body"
    before = row_counts()
    with pytest.raises(RedactionError, match="has no"):
        redact_field(store, entity, entity_id, field, ctx.actor)
    assert row_counts() == before


def test_missing_row_is_not_found(
    store: Store, user: Actor, row_counts: Callable[[], dict[str, int]]
) -> None:
    """A redaction of an unknown id fails and leaves every table as it was."""
    before = row_counts()
    with pytest.raises(NotFoundError):
        redact_field(store, EntityType.DECISION, 999, "body", user)
    assert row_counts() == before


def test_failure_rolls_back_everything(
    monkeypatch: pytest.MonkeyPatch,
    store: Store,
    project: Project,
    user: Actor,
    ctx: WriteContext,
) -> None:
    """Row, events and the redact event commit together or not at all."""
    item = create_item(
        store, project.id, ItemCreate(kind=ItemKind.GOAL, title="t", body="b"), ctx
    )
    before = _events(store, EntityType.ITEM, item.id)

    def fail(*_: object) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(redaction_service.event_db, "redact", fail)
    with pytest.raises(RuntimeError, match="disk full"):
        redact_field(store, EntityType.ITEM, item.id, "body", user)
    assert get_item(store, item.id) == item
    assert _events(store, EntityType.ITEM, item.id) == before
