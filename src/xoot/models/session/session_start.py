"""Input for starting a session."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from xoot.models.fields import Id, Title

MAX_FOCUS_ITEMS = 50


class SessionStart(BaseModel):
    """A title and the items the session means to work on (linked at start)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Title
    focus_item_ids: tuple[Id, ...] = Field(default=(), max_length=MAX_FOCUS_ITEMS)

    @model_validator(mode="after")
    def _unique_focus(self) -> Self:
        """Reject repeated focus items."""
        if len(set(self.focus_item_ids)) != len(self.focus_item_ids):
            raise ValueError("focus items must be unique")
        return self
