"""One planned or applied change to one item."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class ChangeEntry(BaseModel):
    """
    The item key and its changed fields, old and new, with keys for
    references; a move includes the number the item takes.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    before: dict[str, Any]
    after: dict[str, Any]
