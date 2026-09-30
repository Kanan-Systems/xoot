"""POST /api/v1/projects/{p}/backlog/pushes."""

from pydantic import BaseModel, ConfigDict

from xoot.dashboard.requests.fields import RecordKey, Token


class PushRequest(BaseModel):
    """
    Push a backlog item one level up. Always two-phase: the first call
    returns the plan and a confirm_token; send the same body plus the token.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: RecordKey
    confirm_token: Token | None = None
