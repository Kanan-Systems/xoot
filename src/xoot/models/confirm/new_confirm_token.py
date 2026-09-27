"""A confirm-token row about to be inserted."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id, Sha256Hex, Timestamp, ToolName


class NewConfirmToken(BaseModel):
    """
    Every column of a new token except the id and the use stamp. The token
    itself is never stored, only its SHA-256.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    token_sha256: Sha256Hex
    tool: ToolName
    args_sha256: Sha256Hex
    session_id: Id
    expires_at: Timestamp
