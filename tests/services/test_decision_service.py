"""Decisions: owners, keys per owner, the same-goal supersede rule, statuses."""

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.exceptions.decision_error import DecisionError
from xoot.exceptions.integrity_violation_error import IntegrityViolationError
from xoot.models.decision.decision import Decision
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.decision.decision_update import DecisionUpdate
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services.decision_service import (
    create_decision,
    get_decision,
    update_decision,
)
from xoot.store.store import Store

type Tree = tuple[Item, Item, Item, Item]


def _record(
    store: Store, ctx: WriteContext, owner: Item, supersedes: int | None = None
) -> Decision:
    request = DecisionCreate(
        owner_item_id=owner.id, title="d", supersedes_id=supersedes
    )
    return create_decision(store, owner.project_id, request, ctx)


def test_decisions_are_numbered_per_owner(
    store: Store, ctx: WriteContext, work_tree: Tree
) -> None:
    """Each goal, batch and subtask numbers its own decisions."""
    goal, batch, first, second = work_tree
    keys = [
        _record(store, ctx, item).key for item in (goal, batch, batch, first, second)
    ]
    assert keys == [
        "goal-1/decision-1",
        "goal-1/batch-1/decision-1",
        "goal-1/batch-1/decision-2",
        "goal-1/batch-1/subtask-1/decision-1",
        "goal-1/batch-1/subtask-2/decision-1",
    ]


def test_owner_is_required_and_never_backlog(
    store: Store, ctx: WriteContext, work_tree: Tree, capture_on: Callable[..., Item]
) -> None:
    """A decision needs an owner; a backlog item cannot own one."""
    _, _, first, _ = work_tree
    with pytest.raises(ValidationError):
        DecisionCreate.model_validate({"title": "d"})
    with pytest.raises(DecisionError, match="backlog item"):
        _record(store, ctx, capture_on(first))


def test_superseding_within_one_goal(
    store: Store, ctx: WriteContext, work_tree: Tree
) -> None:
    """A subtask decision may supersede its goal's; the older one is marked."""
    goal, _, first, _ = work_tree
    old = _record(store, ctx, goal)
    new = _record(store, ctx, first, supersedes=old.id)
    replaced = get_decision(store, old.id)
    assert (replaced.status, replaced.version) == (DecisionStatus.SUPERSEDED, 2)
    assert new.supersedes_id == old.id


def test_superseding_is_refused_across_goals(
    store: Store,
    ctx: WriteContext,
    project: Project,
    work_tree: Tree,
    make_item: Callable[..., Item],
) -> None:
    """A decision of another goal cannot be superseded."""
    goal, _, _, _ = work_tree
    other = make_item(project, ItemKind.GOAL)
    old = _record(store, ctx, goal)
    with pytest.raises(DecisionError, match="another goal"):
        _record(store, ctx, other, supersedes=old.id)
    assert get_decision(store, old.id).status is DecisionStatus.LOCKED


def test_superseding_never_twice(
    store: Store, ctx: WriteContext, work_tree: Tree
) -> None:
    """The service refuses a second supersede, and so does the schema."""
    goal, batch, _, _ = work_tree
    old = _record(store, ctx, goal)
    _record(store, ctx, batch, supersedes=old.id)
    with pytest.raises(DecisionError, match="already superseded"):
        _record(store, ctx, goal, supersedes=old.id)
    with pytest.raises(IntegrityViolationError):
        with store.write() as conn:
            conn.execute(
                "INSERT INTO decision (project_id, owner_item_id, owner_kind, number, "
                "title, body, status, supersedes_id, version, created_at, updated_at) "
                "VALUES (?, ?, 'goal', 99, 't', '', 'locked', ?, 1, "
                "'2026-09-29T00:00:00.000000Z', '2026-09-29T00:00:00.000000Z')",
                (goal.project_id, goal.id, old.id),
            )


def test_status_changes(store: Store, ctx: WriteContext, work_tree: Tree) -> None:
    """locked and deferred are interchangeable; superseded cannot be set directly."""
    decision = _record(store, ctx, work_tree[0])
    deferred = update_decision(
        store, decision.id, 1, DecisionUpdate(status=DecisionStatus.DEFERRED), ctx
    )
    assert (deferred.status, deferred.version) == (DecisionStatus.DEFERRED, 2)
    with pytest.raises(ValidationError):
        DecisionUpdate(status=DecisionStatus.SUPERSEDED)
    with pytest.raises(ValidationError):
        DecisionCreate(owner_item_id=1, title="x", status=DecisionStatus.SUPERSEDED)


def test_superseded_status_is_final(
    store: Store, ctx: WriteContext, work_tree: Tree
) -> None:
    """A superseded decision's status cannot change."""
    goal, _, _, _ = work_tree
    old = _record(store, ctx, goal)
    _record(store, ctx, goal, supersedes=old.id)
    with pytest.raises(DecisionError, match="superseded"):
        update_decision(
            store, old.id, 2, DecisionUpdate(status=DecisionStatus.LOCKED), ctx
        )


def test_owner_must_be_in_the_project(
    store: Store,
    project: Project,
    other_project: Project,
    make_item: Callable[..., Item],
    ctx: WriteContext,
) -> None:
    """A decision cannot be made on another project's item."""
    foreign = make_item(other_project, ItemKind.GOAL)
    with pytest.raises(CrossProjectError):
        create_decision(
            store, project.id, DecisionCreate(owner_item_id=foreign.id, title="d"), ctx
        )
