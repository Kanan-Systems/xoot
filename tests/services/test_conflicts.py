"""Optimistic updates; the loser learns what changed and who changed it."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from xoot.exceptions.version_conflict_error import VersionConflictError
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.decision.decision_update import DecisionUpdate
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.session.client import Client
from xoot.services.decision_service import create_decision, update_decision
from xoot.services.item_service import get_item, update_item
from xoot.store.store import Store

WORKER_CHANGES = {
    "title": ItemUpdate(title="renamed"),
    "state": ItemUpdate(state="active"),
}


def _stale_update(
    db_path: str, item_id: int, role: tuple[str, str, str], barrier: Any, results: Any
) -> None:
    """Spawned worker: as (actor kind, client, field), update from version 1."""
    kind, client, field = role
    actor = Actor(kind=ActorKind(kind), client=Client(client))
    with Store.open(Path(db_path)) as store:
        barrier.wait(timeout=60)
        try:
            item = update_item(
                store, item_id, 1, WORKER_CHANGES[field], WriteContext(actor=actor)
            )
        except VersionConflictError as exc:
            actors = [(a.kind.value, a.client.value) for a in exc.actors]
            results.put(
                ("lost", field, exc.current_version, exc.changed_fields, actors)
            )
        else:
            results.put(("won", field, item.version, (), [(kind, client)]))


def test_two_stale_updates_exactly_one_wins(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    user: Actor,
    claude: Actor,
) -> None:
    """Both callers read version 1; the second write is refused with details."""
    item = make_item(project, ItemKind.GOAL)
    winner = update_item(
        store, item.id, 1, ItemUpdate(title="renamed"), WriteContext(actor=user)
    )
    with pytest.raises(VersionConflictError) as caught:
        update_item(
            store, item.id, 1, ItemUpdate(state="active"), WriteContext(actor=claude)
        )
    assert winner.version == 2
    assert caught.value.key == "xoot-1"
    assert caught.value.current_version == 2
    assert caught.value.changed_fields == ("title",)
    assert caught.value.actors == (user,)
    assert get_item(store, item.id).state == "open"


def test_conflict_lists_every_change_and_actor_in_order(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    user: Actor,
    claude: Actor,
) -> None:
    """Several intervening writes are all reported, actors in first-seen order."""
    item = make_item(project, ItemKind.GOAL)
    update_item(store, item.id, 1, ItemUpdate(title="one"), WriteContext(actor=claude))
    update_item(store, item.id, 2, ItemUpdate(body="two"), WriteContext(actor=user))
    update_item(
        store, item.id, 3, ItemUpdate(state="active"), WriteContext(actor=claude)
    )
    with pytest.raises(VersionConflictError) as caught:
        update_item(
            store, item.id, 1, ItemUpdate(title="late"), WriteContext(actor=user)
        )
    assert caught.value.current_version == 4
    assert caught.value.changed_fields == ("body", "state", "title")
    assert caught.value.actors == (claude, user)


def test_concurrent_processes_exactly_one_wins(
    store: Store, project: Project, make_item: Callable[..., Item], spawn_workers: Any
) -> None:
    """Two real processes race from version 1; one wins, the loser sees why."""
    item = make_item(project, ItemKind.GOAL)
    outcomes = spawn_workers(
        _stale_update,
        [
            (str(store.path), item.id, ("user", "cli", "title")),
            (str(store.path), item.id, ("claude", "code", "state")),
        ],
    )
    won = [o for o in outcomes if o[0] == "won"]
    lost = [o for o in outcomes if o[0] == "lost"]
    assert len(won) == 1 and len(lost) == 1
    _, winner_field, winner_version, _, winner_actors = won[0]
    _, _, current_version, changed_fields, actors = lost[0]
    assert winner_version == current_version == 2
    assert changed_fields == (winner_field,)
    assert actors == winner_actors


def test_decisions_use_the_same_check(
    store: Store, project: Project, ctx: WriteContext, user: Actor
) -> None:
    """Decision updates are version-checked and explained the same way."""
    decision = create_decision(store, project.id, DecisionCreate(title="d"), ctx)
    update_decision(store, decision.id, 1, DecisionUpdate(body="why"), ctx)
    with pytest.raises(VersionConflictError) as caught:
        update_decision(store, decision.id, 1, DecisionUpdate(title="x"), ctx)
    assert caught.value.key == "xoot-D1"
    assert caught.value.changed_fields == ("body",)
    assert caught.value.actors == (user,)
