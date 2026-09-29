"""
User-only redaction of free text: item and decision titles and bodies, and
project names.

Redaction is the one sanctioned rewrite of history. In one transaction the
row's field becomes "[redacted]" (items and decisions also get a version
bump), every event of the entity loses that field's content, a 'redact'
event records the field name and any version change, never the content, and
every confirm token is deleted: a plan digest pins titles and body digests,
so a stored one could confirm a guess at short redacted text. Every
connection runs with secure_delete on, and a WAL checkpoint follows, so the
old text is gone from the files, not just from the rows.
"""

from typing import Any

from xoot.exceptions.redaction_error import RedactionError
from xoot.models.decision.decision import Decision
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.entity_type import EntityType
from xoot.models.event.event_action import EventAction
from xoot.models.event.redactable_field import RedactableField
from xoot.models.event.redaction_result import RedactionResult
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.project.project import Project
from xoot.repositories.confirm import confirm_token_db
from xoot.repositories.decision import decision_db
from xoot.repositories.event import event_db
from xoot.repositories.item import item_db
from xoot.repositories.project import project_db
from xoot.services.id_checks import check_id
from xoot.services.lookups import require_decision, require_item, require_project
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store

type Redactable = Item | Decision | Project

REDACTED = "[redacted]"
_TEXT = frozenset({RedactableField.TITLE, RedactableField.BODY})
_FIELDS: dict[EntityType, frozenset[RedactableField]] = {
    EntityType.ITEM: _TEXT,
    EntityType.DECISION: _TEXT,
    EntityType.PROJECT: frozenset({RedactableField.NAME}),
}
# A digest of a short secret can be brute-forced, so it goes with the body.
_BODY_DIGEST_KEYS = ("body_sha256", "body_len")


def redact_field(
    store: Store,
    entity: EntityType | str,
    entity_id: int,
    field: RedactableField | str,
    actor: Actor,
) -> RedactionResult:
    """
    Replace a free-text field with "[redacted]" in the row and its history,
    and delete every confirm token in the same transaction.

    The id, entity, field and actor are checked before any SQL. A field that
    is NULL or empty holds nothing to redact and is refused; one that
    already reads "[redacted]" is redacted again (and recorded again).

    Args:
        - store (Store): the database.
        - entity (EntityType | str): item, decision or project.
        - entity_id (int): the row's id.
        - field (RedactableField | str): a field that entity allows.
        - actor (Actor): who redacts; must be the user.

    Returns:
        - result (RedactionResult): the new version (items and decisions),
          the rewritten events, and whether the WAL checkpoint completed.

    Raises:
        - InvalidIdError: entity_id is not an int id.
        - RedactionError: the actor is not the user, the entity/field pair
          cannot be redacted, or the field is NULL or empty.
        - NotFoundError: no such row.
    """
    check_id("entity_id", entity_id)
    entity_type, target = redaction_target(entity, field)
    if actor.kind is not ActorKind.USER:
        raise RedactionError(f"only the user may redact, not {actor.kind}")
    with store.write() as conn:
        scope = WriteScope(conn, WriteContext(actor=actor))
        row = _load(scope, entity_type, entity_id)
        if not getattr(row, target.value):
            raise RedactionError(f"{_public_key(row)} has no {target} to redact")
        redacted = _store_redacted(scope, row, target)
        event_ids = _redact_events(scope, entity_type, entity_id, target)
        before, after = _redact_record(row, target)
        scope.noted(redacted, EventAction.REDACT, after, before)
        confirm_token_db.delete_all(conn)
    purged = store.checkpoint()
    return RedactionResult(
        entity_type=entity_type,
        entity_id=entity_id,
        field=target,
        version=redacted.version if isinstance(redacted, (Item, Decision)) else None,
        redacted_event_ids=tuple(event_ids),
        purged=purged,
    )


def redaction_target(
    entity: EntityType | str, field: RedactableField | str
) -> tuple[EntityType, RedactableField]:
    """
    Check that an entity type allows a field to be redacted, before any SQL.

    Args:
        - entity (EntityType | str): item, decision or project.
        - field (RedactableField | str): the field to redact.

    Returns:
        - target (tuple[EntityType, RedactableField]): the parsed pair.

    Raises:
        - RedactionError: the pair cannot be redacted.
    """
    try:
        entity_type = EntityType(entity)
        target = RedactableField(field)
    except ValueError as exc:
        raise RedactionError(f"cannot redact {entity!r} field {field!r}") from exc
    if target not in _FIELDS.get(entity_type, frozenset()):
        raise RedactionError(f"cannot redact {entity_type} field {target}")
    return entity_type, target


def _load(scope: WriteScope, entity_type: EntityType, entity_id: int) -> Redactable:
    if entity_type is EntityType.ITEM:
        return require_item(scope.conn, entity_id)
    if entity_type is EntityType.DECISION:
        return require_decision(scope.conn, entity_id)
    return require_project(scope.conn, entity_id)


def _public_key(row: Redactable) -> str:
    """The key a user knows the row by; the row id is internal."""
    if isinstance(row, Project):
        return row.key_prefix
    return row.key


def _store_redacted(
    scope: WriteScope, row: Redactable, field: RedactableField
) -> Redactable:
    """Overwrite the field on the row itself; versioned rows get a bump."""
    if isinstance(row, Project):
        return project_db.set_name(scope.conn, row.id, REDACTED)
    update = {
        field.value: REDACTED,
        "version": row.version + 1,
        "updated_at": scope.now,
    }
    if isinstance(row, Item):
        item = row.model_copy(update=update)
        item_db.update(scope.conn, item, row.version)
        return item
    decision = row.model_copy(update=update)
    decision_db.update(scope.conn, decision, row.version)
    return decision


def _redact_record(
    row: Redactable, field: RedactableField
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """The redact event's before/after: field name and version, no content."""
    after: dict[str, Any] = {"field": field.value}
    if not isinstance(row, (Item, Decision)):
        return None, after
    return {"version": row.version}, {**after, "version": row.version + 1}


def _redact_events(
    scope: WriteScope, entity_type: EntityType, entity_id: int, field: RedactableField
) -> list[int]:
    """Scrub the field from every event of the entity; return those rewritten."""
    rewritten = []
    for event in event_db.list_for_entity(scope.conn, entity_type, entity_id):
        before = _scrub(event.before, field)
        after = _scrub(event.after, field)
        if (before, after) != (event.before, event.after):
            event_db.redact(scope.conn, event.id, before, after, scope.now)
            rewritten.append(event.id)
    return rewritten


def _scrub(
    payload: dict[str, Any] | None, field: RedactableField
) -> dict[str, Any] | None:
    if payload is None:
        return None
    scrubbed = dict(payload)
    # Only non-empty text holds content; a recorded NULL or "" stays as is.
    if scrubbed.get(field.value):
        scrubbed[field.value] = REDACTED
    if field is RedactableField.BODY:
        for key in _BODY_DIGEST_KEYS:
            if key in scrubbed:
                scrubbed[key] = None
    return scrubbed
