"""An item's key, version and state as a write left it."""

from pydantic import BaseModel, ConfigDict


class ItemVersion(BaseModel):
    """
    Enough for the next write to pass a correct expected_version: the
    item's current key, its version and its state after the write.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    version: int
    state: str
