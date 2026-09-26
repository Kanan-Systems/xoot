"""Decisions: keys, superseding, and status rules."""

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.exceptions.decision_error import DecisionError
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


def test_keys_use_their_own_counter(
    store: Store, project: Project, make_item: Callable[..., Item], ctx: WriteContext
) -> None:
    """Decision keys are <prefix>-D<n>, independent of item numbers."""
    make_item(project, ItemKind.GOAL)
    first = create_decision(store, project.id, DecisionCreate(title="a"), ctx)
    second = create_decision(store, project.id, DecisionCreate(title="b"), ctx)
    assert (first.key, second.key) == ("xoot-D1", "xoot-D2")


def test_superseding_marks_the_older_decision(
    store: Store, project: Project, ctx: WriteContext
) -> None:
    """The new decision and the older one's status change commit together."""
    old = create_decision(store, project.id, DecisionCreate(title="old"), ctx)
    new = create_decision(
        store, project.id, DecisionCreate(title="new", supersedes_id=old.id), ctx
    )
    replaced = get_decision(store, old.id)
    assert (replaced.status, replaced.version) == (DecisionStatus.SUPERSEDED, 2)
    assert new.supersedes_id == old.id
    with pytest.raises(DecisionError, match="already superseded"):
        create_decision(
            store, project.id, DecisionCreate(title="again", supersedes_id=old.id), ctx
        )
    with pytest.raises(DecisionError, match="superseded"):
        update_decision(
            store, old.id, 2, DecisionUpdate(status=DecisionStatus.LOCKED), ctx
        )


def test_status_changes(store: Store, project: Project, ctx: WriteContext) -> None:
    """locked and deferred are interchangeable; superseded cannot be set directly."""
    decision = create_decision(store, project.id, DecisionCreate(title="d"), ctx)
    deferred = update_decision(
        store, decision.id, 1, DecisionUpdate(status=DecisionStatus.DEFERRED), ctx
    )
    assert (deferred.status, deferred.version) == (DecisionStatus.DEFERRED, 2)
    with pytest.raises(ValidationError):
        DecisionUpdate(status=DecisionStatus.SUPERSEDED)
    with pytest.raises(ValidationError):
        DecisionCreate(title="x", status=DecisionStatus.SUPERSEDED)


def test_scope_item_must_be_in_the_project(
    store: Store,
    project: Project,
    other_project: Project,
    make_item: Callable[..., Item],
    ctx: WriteContext,
) -> None:
    """A decision cannot be scoped to another project's item."""
    foreign = make_item(other_project, ItemKind.GOAL)
    with pytest.raises(CrossProjectError):
        create_decision(
            store, project.id, DecisionCreate(title="d", scope_item_id=foreign.id), ctx
        )
