"""What decision_record, decision_update and decision_get return."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.decision_detail import DecisionDetail


class DecisionOutput(BaseModel):
    """One decision in full, and the project it belongs to."""

    model_config = ConfigDict(frozen=True)

    project: str
    decision: DecisionDetail
