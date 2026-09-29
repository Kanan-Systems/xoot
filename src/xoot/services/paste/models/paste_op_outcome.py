"""What one op of a paste block did."""

from pydantic import BaseModel, ConfigDict

from xoot.services.paste.models.paste_change import PasteChange


class PasteOpOutcome(BaseModel):
    """
    One op's effect: the key it created or targeted, the ref it defined,
    and its field changes. A cover also names the backlog item it closed in
    changes; a push or move lists each key change.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int
    op: str
    key: str | None
    ref: str | None = None
    created: bool = False
    changes: tuple[PasteChange, ...] = ()
