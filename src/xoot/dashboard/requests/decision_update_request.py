"""PATCH /api/v1/projects/{p}/decisions/{key}."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.fields import Body, Id, Title, reject_explicit_none

CHANGES = ("title", "body", "status")


class DecisionUpdateRequest(BaseModel):
    """New title, body or status of a decision, based on expected_version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    expected_version: Id
    title: Title | None = None
    body: Body | None = None
    status: DecisionStatus | None = None

    @model_validator(mode="after")
    def _some_change(self) -> Self:
        """Require at least one change and refuse explicit nulls."""
        reject_explicit_none(self, CHANGES)
        if not self.model_fields_set & set(CHANGES):
            raise ValueError("send at least one of title, body or status")
        return self
