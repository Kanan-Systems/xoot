"""A decision as it appears in lists."""

from pydantic import BaseModel, ConfigDict

from xoot.models.decision.decision_status import DecisionStatus


class DecisionSummary(BaseModel):
    """
    A decision's key (<owner key>/decision-<n>), title, status, the item it
    was made on, the decision it supersedes, and its version.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    title: str
    status: DecisionStatus
    owner: str | None
    supersedes: str | None
    version: int
    updated_at: str
