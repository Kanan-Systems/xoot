"""An item a paste touched, as the block leaves it."""

from pydantic import BaseModel, ConfigDict


class PasteItemState(BaseModel):
    """The key, final version and final state of one touched item."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    version: int
    state: str
