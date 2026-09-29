"""The backlog_push op: move a backlog item one level up."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from xoot.services.paste.models.fields import ItemKeyOrRef


class BacklogPushOp(BaseModel):
    """
    Pushes one open backlog item from its batch to its goal, or from its
    goal to the project. The dry-run plan the user confirms stands in for
    the tool's confirm token.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    op: Literal["backlog_push"]
    key: ItemKeyOrRef
