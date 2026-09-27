"""What one op of a paste block did."""

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.session.disposition import Disposition
from xoot.services.paste.models.paste_change import PasteChange


class PasteOpOutcome(BaseModel):
    """
    One op's effect: the key it created or targeted (the session key for
    session ops), the ref it defined, its field changes, for a reparent the
    descendants carried along unchanged, and for a close every disposition
    by item key.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int
    op: str
    key: str | None
    ref: str | None = None
    created: bool = False
    changes: tuple[PasteChange, ...] = ()
    carried: tuple[str, ...] = ()
    dispositions: dict[str, Disposition] = Field(default_factory=dict)
