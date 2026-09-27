"""The key-based changes of a decision_update: the MCP tool's argument and a paste op's field."""

from pydantic import BaseModel, ConfigDict

from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.fields import Body, Title


class DecisionChangesInput(BaseModel):
    """Fields to change; leave a field out to keep it. None can be cleared."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Title | None = None
    body: Body | None = None
    status: DecisionStatus | None = None
