"""
Every service entry point refuses a non-int or bool id or version before
any SQL runs, so nothing can be selected or written through type affinity.
"""

from collections.abc import Callable
from dataclasses import dataclass

import pytest

from xoot.exceptions.invalid_id_error import InvalidIdError
from xoot.models.decision.decision import Decision
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.decision.decision_update import DecisionUpdate
from xoot.models.event.actor import Actor
from xoot.models.event.entity_type import EntityType
from xoot.models.event.redactable_field import RedactableField
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.item.tree_query import TreeQuery
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.models.session.session_start import SessionStart
from xoot.models.workflow.workflow_change import WorkflowChange
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.services import (
    decision_service,
    item_service,
    project_service,
    redaction_service,
    session_close_service,
    session_service,
    subtree_service,
    tree_service,
    workflow_service,
)
from xoot.services.id_checks import check_id
from xoot.store.store import Store

BAD_VALUES = ["5", "05", "5.0", True, False, 1.0, None]


@dataclass(frozen=True)
class Env:
    """Valid rows and actors, so only the argument under test is wrong."""

    batch: Item
    subtask: Item
    decision: Decision
    session: Session
    user: Actor
    ctx: WriteContext


type Call = Callable[[Store, Env, object], object]

CALLS: dict[str, Call] = {
    "add_alias.project_id": lambda s, e, v: project_service.add_alias(
        s, v, "al", e.ctx
    ),
    "add_path.project_id": lambda s, e, v: project_service.add_path(
        s, v, "/new", e.ctx
    ),
    "get_project.project_id": lambda s, e, v: project_service.get_project(s, v),
    "start_session.project_id": lambda s, e, v: session_service.start_session(
        s, v, SessionStart(title="t"), e.user
    ),
    "get_session.session_id": lambda s, e, v: session_service.get_session(s, v),
    "preview_close.session_id": lambda s, e, v: session_close_service.preview_close(
        s, v, SessionClose()
    ),
    "close_session.session_id": lambda s, e, v: session_close_service.close_session(
        s, v, SessionClose(), e.user
    ),
    "create_item.project_id": lambda s, e, v: item_service.create_item(
        s, v, ItemCreate(kind=ItemKind.GOAL, title="t"), e.ctx
    ),
    "capture.session_id": lambda s, e, v: item_service.capture(
        s, v, ItemDraft(title="t"), e.user
    ),
    "update_item.item_id": lambda s, e, v: item_service.update_item(
        s, v, 1, ItemUpdate(title="t"), e.ctx
    ),
    "update_item.expected_version": lambda s, e, v: item_service.update_item(
        s, e.subtask.id, v, ItemUpdate(title="t"), e.ctx
    ),
    "get_item.item_id": lambda s, e, v: item_service.get_item(s, v),
    "create_decision.project_id": lambda s, e, v: decision_service.create_decision(
        s, v, DecisionCreate(title="t"), e.ctx
    ),
    "update_decision.decision_id": lambda s, e, v: decision_service.update_decision(
        s, v, 1, DecisionUpdate(title="t"), e.ctx
    ),
    "update_decision.expected_version": lambda s, e, v: (
        decision_service.update_decision(
            s, e.decision.id, v, DecisionUpdate(title="t"), e.ctx
        )
    ),
    "get_decision.decision_id": lambda s, e, v: decision_service.get_decision(s, v),
    "get_active_workflow.project_id": lambda s, e, v: (
        workflow_service.get_active_workflow(s, v)
    ),
    "set_workflow.project_id": lambda s, e, v: workflow_service.set_workflow(
        s,
        v,
        WorkflowChange(definition=WorkflowDefinition.default()),
        e.ctx,
    ),
    "tree.project_id": lambda s, e, v: tree_service.tree(s, v, TreeQuery()),
    "preview_drop.item_id": lambda s, e, v: subtree_service.preview_drop(s, v),
    "apply_drop.item_id": lambda s, e, v: subtree_service.apply_drop(s, v, 1, e.ctx),
    "apply_drop.expected_version": lambda s, e, v: subtree_service.apply_drop(
        s, e.subtask.id, v, e.ctx
    ),
    "preview_reparent.item_id": lambda s, e, v: subtree_service.preview_reparent(
        s, v, e.batch.id
    ),
    "preview_reparent.new_parent_id": lambda s, e, v: subtree_service.preview_reparent(
        s, e.subtask.id, v
    ),
    "apply_reparent.item_id": lambda s, e, v: subtree_service.apply_reparent(
        s, v, e.batch.id, 1, e.ctx
    ),
    "apply_reparent.new_parent_id": lambda s, e, v: subtree_service.apply_reparent(
        s, e.subtask.id, v, 1, e.ctx
    ),
    "apply_reparent.expected_version": lambda s, e, v: subtree_service.apply_reparent(
        s, e.subtask.id, e.batch.id, v, e.ctx
    ),
    "redact_field.entity_id": lambda s, e, v: redaction_service.redact_field(
        s, EntityType.ITEM, v, RedactableField.TITLE, e.user
    ),
}

# None is a valid new_parent_id: it unfiles a subtask.
CASES = [
    (name, value)
    for name in CALLS
    for value in BAD_VALUES
    if not (value is None and name.endswith(".new_parent_id"))
]


@pytest.fixture(name="env")
def fixture_env(
    store: Store,
    project: Project,
    ctx: WriteContext,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
) -> Env:
    """One of everything an entry point can point at, all valid."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    return Env(
        batch=batch,
        subtask=make_item(project, ItemKind.SUBTASK, parent_id=batch.id),
        decision=decision_service.create_decision(
            store, project.id, DecisionCreate(title="d"), ctx
        ),
        session=make_session(project),
        user=ctx.actor,
        ctx=ctx,
    )


@pytest.mark.parametrize(("call", "value"), CASES)
def test_bad_id_is_refused_before_any_sql(
    store: Store,
    env: Env,
    row_counts: Callable[[], dict[str, int]],
    call: str,
    value: object,
) -> None:
    """The guard fires first: no statement runs and no row changes."""
    before = row_counts()
    statements: list[str] = []
    store.conn.set_trace_callback(statements.append)
    try:
        with pytest.raises(InvalidIdError) as caught:
            CALLS[call](store, env, value)
    finally:
        store.conn.set_trace_callback(None)
    assert not statements
    assert row_counts() == before
    assert caught.value.name == call.split(".")[1]
    assert caught.value.type_name == type(value).__name__


@pytest.mark.parametrize("value", [0, -1, 2**63])
def test_out_of_range_int_is_refused(value: int) -> None:
    """Ids SQLite cannot store (or never assigns) are refused too."""
    with pytest.raises(InvalidIdError, match="item_id must be an int"):
        check_id("item_id", value)


def test_valid_ids_pass_through(store: Store, env: Env) -> None:
    """A plain int reaches the service unchanged."""
    assert item_service.get_item(store, env.subtask.id) == env.subtask
    assert check_id("item_id", 2**63 - 1) == 2**63 - 1
