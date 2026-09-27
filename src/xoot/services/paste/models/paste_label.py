"""How the plan names a record the block touched."""

from pydantic import BaseModel, ConfigDict


class PasteLabel(BaseModel):
    """
    The kind (goal, batch, subtask or decision) and current title of one
    touched record, for the plan shown on the terminal only.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str
    title: str
