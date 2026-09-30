"""POST /api/v1/projects/{p}/items."""

from pydantic import BaseModel, ConfigDict

from xoot.dashboard.requests.fields import RecordKey
from xoot.models.fields import Body, Title
from xoot.server.schemas.literals import WorkKind


class ItemCreateRequest(BaseModel):
    """
    A new goal, batch or subtask. A goal takes no parent, a batch a goal and
    a subtask a batch; backlog items come from capture.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: WorkKind
    title: Title
    body: Body = ""
    parent: RecordKey | None = None
