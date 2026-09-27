"""A decision a paste touched, as the block leaves it."""

from pydantic import BaseModel, ConfigDict

from xoot.models.decision.decision_status import DecisionStatus


class PasteDecisionState(BaseModel):
    """The key, final version and final status of one touched decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    version: int
    status: DecisionStatus
