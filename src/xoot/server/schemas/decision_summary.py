"""A decision as it appears in lists."""

from pydantic import BaseModel, ConfigDict

from xoot.models.decision.decision_status import DecisionStatus


class DecisionSummary(BaseModel):
    """A decision's key, title, status, references and version."""

    model_config = ConfigDict(frozen=True)

    key: str
    title: str
    status: DecisionStatus
    scope: str | None
    supersedes: str | None
    version: int
    updated_at: str
