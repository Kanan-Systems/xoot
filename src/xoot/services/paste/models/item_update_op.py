"""The item_update op: change one item."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id
from xoot.models.item.item_changes_input import ItemChangesInput
from xoot.services.paste.models.fields import ItemKeyOrRef


class ItemUpdateOp(BaseModel):
    """
    Changes one item with the item_update tool's changes model and rules.
    expected_version is required for an existing item and must be omitted
    for one created in the block (its key is a ref). The parent and
    awaited decision inside changes are checked against the key grammar
    when the op runs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    op: Literal["item_update"]
    key: ItemKeyOrRef
    expected_version: Id | None = None
    changes: ItemChangesInput
