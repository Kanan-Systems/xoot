"""The effect of a subtree drop, a reparent or a backlog push."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.change_entry import ChangeEntry


class SubtreeOutput(BaseModel):
    """Every row that changes, in write order; a move lists each key change."""

    model_config = ConfigDict(frozen=True)

    root: str
    changes: list[ChangeEntry]
