"""POST /api/v1/projects/{p}/backlog/covers."""

from pydantic import BaseModel, ConfigDict

from xoot.dashboard.requests.fields import RecordKey


class CoverRequest(BaseModel):
    """
    Turn a backlog item into a subtask and close it. A goal-level item needs
    the batch to cover it in; a batch-level one is covered in its own batch.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: RecordKey
    batch: RecordKey | None = None
