"""A confirm-token row about to be inserted."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id, Sha256Hex, Timestamp, ToolName


class NewConfirmToken(BaseModel):
    """
    Every column of a new token except the id and the use stamp. The token
    itself is never stored, only its SHA-256. It is bound to one project,
    and plan_sha256 binds it to the plan the preview showed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    token_sha256: Sha256Hex
    project_id: Id
    tool: ToolName
    args_sha256: Sha256Hex
    plan_sha256: Sha256Hex
    expires_at: Timestamp
