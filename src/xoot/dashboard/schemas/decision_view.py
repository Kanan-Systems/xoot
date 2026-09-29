"""What GET /api/v1/decisions/{key} returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.decision_detail import DecisionDetail


class DecisionView(BaseModel):
    """One decision with its body."""

    model_config = ConfigDict(frozen=True)

    decision: DecisionDetail
