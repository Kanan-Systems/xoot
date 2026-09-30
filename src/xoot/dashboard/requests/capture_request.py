"""POST /api/v1/projects/{p}/backlog."""

from pydantic import BaseModel, ConfigDict

from xoot.dashboard.requests.fields import RecordKey
from xoot.models.fields import Body, Title


class CaptureRequest(BaseModel):
    """Open work found on an item, with a body saying why it needs doing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    found_on: RecordKey
    title: Title
    body: Body
