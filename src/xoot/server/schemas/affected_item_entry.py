"""One item as a subtree drop or reparent left it."""

from pydantic import BaseModel, ConfigDict


class AffectedItemEntry(BaseModel):
    """The item's state, parent and new version, enough for the next item_update."""

    model_config = ConfigDict(frozen=True)

    key: str
    state: str
    parent: str | None
    version: int
