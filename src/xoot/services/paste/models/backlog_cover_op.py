"""The backlog_cover op: turn a backlog item into a subtask."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from xoot.services.paste.models.fields import ItemKeyOrRef, RefName


class BacklogCoverOp(BaseModel):
    """
    Covers one open backlog item as the backlog_cover tool does. batch is
    required for an item on a goal or on the project. ref names the new
    subtask for later ops.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    op: Literal["backlog_cover"]
    ref: RefName | None = None
    key: ItemKeyOrRef
    batch: ItemKeyOrRef | None = None
