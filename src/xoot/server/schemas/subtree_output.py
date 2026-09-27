"""The effect of a subtree drop or reparent."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.change_entry import ChangeEntry


class SubtreeOutput(BaseModel):
    """Every row that changes, and the descendants carried along unchanged."""

    model_config = ConfigDict(frozen=True)

    root: str
    changes: list[ChangeEntry]
    carried: list[str]
