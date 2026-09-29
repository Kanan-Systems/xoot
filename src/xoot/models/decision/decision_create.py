"""Input for recording a decision."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.fields import Body, Id, Title


class DecisionCreate(BaseModel):
    """
    A new decision on the goal, batch or subtask it was made on. When
    supersedes_id is set the older decision, on the same goal, becomes
    superseded in the same transaction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    owner_item_id: Id
    title: Title
    body: Body = ""
    status: DecisionStatus = DecisionStatus.LOCKED
    supersedes_id: Id | None = None

    @model_validator(mode="after")
    def _not_born_superseded(self) -> Self:
        """Superseded is only reached when a newer decision replaces this one."""
        if self.status is DecisionStatus.SUPERSEDED:
            raise ValueError("a new decision cannot start superseded")
        return self
