"""
A redacted secret leaves no bytes in the database or its WAL, for every
redactable field. A plain sqlite3 connection with secure_delete off is the
negative control: it shows the scan does find bytes an overwrite leaves
behind, so a zero from the xoot path means the bytes are really gone.
"""

import sqlite3
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest

from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.decision.decision_update import DecisionUpdate
from xoot.models.event.entity_type import EntityType
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.project.project_registration import ProjectRegistration
from xoot.models.session.session_close import SessionClose
from xoot.models.session.session_start import SessionStart
from xoot.services.decision_service import create_decision, update_decision
from xoot.services.item_service import create_item, get_item, update_item
from xoot.services.project_service import add_alias, register_project
from xoot.services.redaction_service import REDACTED, redact_field
from xoot.services.session_close_service import close_session
from xoot.services.session_service import start_session
from xoot.store.store import Store

type Planted = tuple[EntityType, int, str]
type Planter = Callable[[Store, Project, WriteContext, str], Planted]


def _overflow(secret: str) -> str:
    """A body-sized text whose secret sits on an overflow page."""
    return "x" * 20000 + secret + "y" * 12000


def _disk_hits(db_path: Path, secret: str) -> int:
    """Occurrences of the secret in the raw bytes of the database and its WAL."""
    needle = secret.encode()
    files = [db_path, db_path.with_name(db_path.name + "-wal")]
    return sum(path.read_bytes().count(needle) for path in files if path.exists())


def _item(field: str, overflow: bool) -> Planter:
    def plant(s: Store, p: Project, ctx: WriteContext, secret: str) -> Planted:
        text = _overflow(secret) if overflow else secret
        request = ItemCreate(kind=ItemKind.GOAL, **{"title": "t", field: text})
        item = create_item(s, p.id, request, ctx)
        update_item(s, item.id, 1, ItemUpdate(state="active"), ctx)
        return EntityType.ITEM, item.id, field

    return plant


def _decision(field: str, overflow: bool) -> Planter:
    def plant(s: Store, p: Project, ctx: WriteContext, secret: str) -> Planted:
        text = _overflow(secret) if overflow else secret
        request = DecisionCreate(**{"title": "t", field: text})
        decision = create_decision(s, p.id, request, ctx)
        deferred = DecisionUpdate(status=DecisionStatus.DEFERRED)
        update_decision(s, decision.id, 1, deferred, ctx)
        return EntityType.DECISION, decision.id, field

    return plant


def _session(field: str, overflow: bool) -> Planter:
    def plant(s: Store, p: Project, ctx: WriteContext, secret: str) -> Planted:
        text = _overflow(secret) if overflow else secret
        title = text if field == "title" else "s"
        summary = text if field == "summary" else None
        session = start_session(s, p.id, SessionStart(title=title), ctx.actor).session
        close_session(s, session.id, SessionClose(summary=summary), ctx.actor)
        return EntityType.SESSION, session.id, field

    return plant


def _project_name(s: Store, _: Project, ctx: WriteContext, secret: str) -> Planted:
    registration = ProjectRegistration(key_prefix="leak", name=secret)
    project = register_project(s, registration, ctx.actor)
    add_alias(s, project.id, "lk", ctx)
    return EntityType.PROJECT, project.id, "name"


PLANTERS: dict[str, Planter] = {
    "item-title": _item("title", overflow=False),
    "item-body": _item("body", overflow=False),
    "item-body-overflow": _item("body", overflow=True),
    "decision-title": _decision("title", overflow=False),
    "decision-body": _decision("body", overflow=False),
    "decision-body-overflow": _decision("body", overflow=True),
    "session-title": _session("title", overflow=False),
    "session-summary": _session("summary", overflow=False),
    "session-summary-overflow": _session("summary", overflow=True),
    "project-name": _project_name,
}


def test_raw_overwrite_without_secure_delete_leaves_the_secret(
    store: Store, project: Project, ctx: WriteContext
) -> None:
    """Negative control: without secure_delete the freed bytes stay on disk."""
    secret = f"secret-{uuid.uuid4().hex}"
    request = ItemCreate(kind=ItemKind.GOAL, title="t", body=_overflow(secret))
    item = create_item(store, project.id, request, ctx)
    raw = sqlite3.connect(store.path, autocommit=True)
    try:
        raw.execute("PRAGMA secure_delete = OFF")
        raw.execute("UPDATE item SET body = ? WHERE id = ?", (REDACTED, item.id))
        busy = raw.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]
    finally:
        raw.close()
    assert busy == 0
    assert get_item(store, item.id).body == REDACTED
    assert _disk_hits(store.path, secret) > 0


@pytest.mark.parametrize("case", list(PLANTERS))
def test_redacted_secret_leaves_no_bytes(
    store: Store, project: Project, ctx: WriteContext, case: str
) -> None:
    """Through xoot, every copy is gone from the database and the WAL."""
    secret = f"secret-{uuid.uuid4().hex}"
    entity_type, entity_id, field = PLANTERS[case](store, project, ctx, secret)
    assert _disk_hits(store.path, secret) > 0
    result = redact_field(store, entity_type, entity_id, field, ctx.actor)
    assert result.purged
    assert _disk_hits(store.path, secret) == 0
