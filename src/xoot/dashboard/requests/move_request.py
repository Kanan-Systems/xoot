"""POST /api/v1/projects/{p}/moves."""

from pydantic import BaseModel, ConfigDict

from xoot.dashboard.requests.fields import RecordKey, Token
from xoot.models.fields import Id


class MoveRequest(BaseModel):
    """
    Move a batch to another goal, or a subtask to another batch, with its
    subtree. An item with children first returns a preview and a
    confirm_token; send the same body plus the token to apply.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: RecordKey
    parent: RecordKey
    expected_version: Id
    confirm_token: Token | None = None
