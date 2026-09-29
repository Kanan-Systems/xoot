"""Every id, number and version field is a strict int; bool is refused."""

from collections.abc import Callable

import pytest
from pydantic import TypeAdapter, ValidationError

from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client
from xoot.models.fields import Id
from xoot.models.item.item_change import ItemChange
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.item.tree_query import TreeQuery

NON_INTS = ["5", "05", "5.0", True, False, 1.0]
USER = Actor(kind=ActorKind.USER, client=Client.CLI)

BUILDERS: dict[str, Callable[[object], object]] = {
    "Id": TypeAdapter(Id).validate_python,
    "ItemChange.item_id": lambda v: ItemChange(
        item_id=v, key="goal-1", before={}, after={}
    ),
    "ItemCreate.parent_id": lambda v: ItemCreate(
        kind=ItemKind.SUBTASK, title="t", parent_id=v
    ),
    "ItemUpdate.awaiting_decision_id": lambda v: ItemUpdate(awaiting_decision_id=v),
    "ItemCreate.found_on_item_id": lambda v: ItemCreate(
        kind=ItemKind.BACKLOG, title="t", found_on_item_id=v
    ),
    "DecisionCreate.owner_item_id": lambda v: DecisionCreate(
        owner_item_id=v, title="t"
    ),
    "DecisionCreate.supersedes_id": lambda v: DecisionCreate(
        owner_item_id=1, title="t", supersedes_id=v
    ),
    "TreeQuery.root_id": lambda v: TreeQuery(root_id=v),
}
REQUIRED = ("Id", "ItemChange.item_id")


@pytest.mark.parametrize(
    ("field", "value"),
    [(field, value) for field in BUILDERS for value in NON_INTS]
    + [(field, None) for field in REQUIRED],
)
def test_non_int_ids_are_refused(field: str, value: object) -> None:
    """Strings, bools, floats (and None where an id is required) fail."""
    with pytest.raises(ValidationError, match="valid integer"):
        BUILDERS[field](value)


@pytest.mark.parametrize("field", list(BUILDERS))
def test_plain_ints_are_accepted(field: str) -> None:
    """The strictness only removes coercion; real ids still validate."""
    assert BUILDERS[field](5) is not None
