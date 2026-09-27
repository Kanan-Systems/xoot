"""
A refused redaction names the record by its public key (xoot-3, xoot-D1,
xoot-S1), never by its internal row id.
"""

from collections.abc import Callable

import pytest

from xoot.exceptions.redaction_error import RedactionError
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.session.session_start import SessionStart
from xoot.services.decision_service import create_decision
from xoot.services.redaction_service import redact_field
from xoot.services.session_service import start_session
from xoot.store.store import Store


def test_item_is_named_by_key(
    project: Project, store: Store, ctx: WriteContext, make_item: Callable[..., Item]
) -> None:
    """Item 3's empty body is refused as xoot-3, not as item id 3."""
    for _ in range(2):
        make_item(project, ItemKind.GOAL)
    item = make_item(project, ItemKind.GOAL)
    with pytest.raises(RedactionError, match="^xoot-3 has no body to redact$"):
        redact_field(store, "item", item.id, "body", ctx.actor)


def test_decision_is_named_by_key(
    project: Project, store: Store, ctx: WriteContext
) -> None:
    """An empty decision body is refused as xoot-D1."""
    decision = create_decision(store, project.id, DecisionCreate(title="d"), ctx)
    with pytest.raises(RedactionError, match="^xoot-D1 has no body to redact$"):
        redact_field(store, "decision", decision.id, "body", ctx.actor)


def test_session_is_named_by_key(
    project: Project, other_project: Project, store: Store, ctx: WriteContext
) -> None:
    """Session 1 of project xoot is xoot-S1 even when its row id is 2."""
    start_session(store, other_project.id, SessionStart(title="s"), ctx.actor)
    started = start_session(store, project.id, SessionStart(title="s"), ctx.actor)
    assert started.session.id == 2
    with pytest.raises(RedactionError, match="^xoot-S1 has no summary to redact$"):
        redact_field(store, "session", started.session.id, "summary", ctx.actor)
