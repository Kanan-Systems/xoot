"""What GET /api/v1/projects/{prefix}/decisions returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.decision_summary import DecisionSummary


class DecisionsView(BaseModel):
    """Decisions, newest first."""

    model_config = ConfigDict(frozen=True)

    project: str
    decisions: list[DecisionSummary]
    truncated: bool
