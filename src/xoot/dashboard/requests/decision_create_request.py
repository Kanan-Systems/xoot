"""POST /api/v1/projects/{p}/decisions."""

from pydantic import BaseModel, ConfigDict

from xoot.dashboard.requests.fields import RecordKey
from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.fields import Body, Title


class DecisionCreateRequest(BaseModel):
    """
    A decision on the goal, batch or subtask it was made on; supersedes names
    an older decision of the same goal, which becomes superseded.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    owner: RecordKey
    title: Title
    body: Body = ""
    status: DecisionStatus = DecisionStatus.LOCKED
    supersedes: RecordKey | None = None
