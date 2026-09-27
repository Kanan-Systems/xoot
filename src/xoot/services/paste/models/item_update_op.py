"""The item_update op: change one item."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id
from xoot.server.schemas.item_changes_input import ItemChangesInput
from xoot.services.paste.models.fields import KeyOrRef


class ItemUpdateOp(BaseModel):
    """
    Changes one item with the item_update tool's changes model and rules.
    expected_version is required for an existing item and must be omitted
    for one created in the block (its key is a ref).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    op: Literal["item_update"]
    key: KeyOrRef
    expected_version: Id | None = None
    changes: ItemChangesInput
