"""Input for a partial decision update."""

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, model_validator

from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.fields import (
    Body,
    Title,
    provided_fields,
    reject_explicit_none,
)


class DecisionUpdate(BaseModel):
    """Only fields the caller sets are changed; none of them can be cleared."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Title | None = None
    body: Body | None = None
    status: DecisionStatus | None = None

    @model_validator(mode="after")
    def _allowed(self) -> Self:
        """Reject clearing fields and setting superseded directly."""
        reject_explicit_none(self, ("title", "body", "status"))
        if self.status is DecisionStatus.SUPERSEDED:
            raise ValueError("superseded is set by recording a newer decision")
        return self

    def provided(self) -> dict[str, Any]:
        """
        Return the fields the caller explicitly set.

        Returns:
            - fields (dict[str, Any]): field name to requested value.
        """
        return provided_fields(self)
