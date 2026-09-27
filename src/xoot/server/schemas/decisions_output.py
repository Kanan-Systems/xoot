"""What decisions_list returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.decision_summary import DecisionSummary
from xoot.server.schemas.literals import ResolvedBy


class DecisionsOutput(BaseModel):
    """Decisions, newest first; truncated when the cap hid decisions."""

    model_config = ConfigDict(frozen=True)

    project: str
    resolved_by: ResolvedBy
    decisions: list[DecisionSummary]
    truncated: bool
