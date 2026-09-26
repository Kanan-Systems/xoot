"""One planned or applied change to one item."""

from typing import Any

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id


class ItemChange(BaseModel):
    """
    The fields that change on one item, old and new values side by side.
    Previews return these without writing; applies write exactly these.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: Id
    key: str
    before: dict[str, Any]
    after: dict[str, Any]
