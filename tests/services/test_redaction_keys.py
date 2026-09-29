"""
A refused redaction names the record by its public key (goal-3,
goal-1/decision-1, the project prefix), never by its internal row id.
"""

from collections.abc import Callable

import pytest

from xoot.exceptions.redaction_error import RedactionError
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services.decision_service import create_decision
from xoot.services.redaction_service import redact_field
from xoot.store.store import Store


def test_item_is_named_by_key(
    project: Project,
    other_project: Project,
    store: Store,
    ctx: WriteContext,
    make_item: Callable[..., Item],
) -> None:
    """goal-2's empty body is refused as goal-2, not as its row id 3."""
    make_item(project, ItemKind.GOAL)
    make_item(other_project, ItemKind.GOAL)
    item = make_item(project, ItemKind.GOAL)
    assert item.id == 3
    with pytest.raises(RedactionError, match="^goal-2 has no body to redact$"):
        redact_field(store, "item", item.id, "body", ctx.actor)


def test_decision_is_named_by_key(
    project: Project, store: Store, ctx: WriteContext, make_item: Callable[..., Item]
) -> None:
    """An empty decision body is refused as goal-1/decision-1."""
    goal = make_item(project, ItemKind.GOAL)
    request = DecisionCreate(owner_item_id=goal.id, title="d")
    decision = create_decision(store, project.id, request, ctx)
    with pytest.raises(
        RedactionError, match="^goal-1/decision-1 has no body to redact$"
    ):
        redact_field(store, "decision", decision.id, "body", ctx.actor)


@pytest.mark.parametrize(
    ("entity", "field"), [("session", "title"), ("item", "summary"), ("item", "name")]
)
# Each fixture the test needs is one argument.
def test_sessions_and_summaries_are_gone(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    project: Project,
    store: Store,
    ctx: WriteContext,
    make_item: Callable[..., Item],
    entity: str,
    field: str,
) -> None:
    """Only items, decisions and projects, and their text fields, redact."""
    item = make_item(project, ItemKind.GOAL)
    with pytest.raises(RedactionError, match="cannot redact"):
        redact_field(store, entity, item.id, field, ctx.actor)
