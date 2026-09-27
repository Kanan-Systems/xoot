"""The claim a caller presents to apply a previewed change."""

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.fields import Sha256Hex, ToolName

TOKEN_MAX = 128


class Confirmation(BaseModel):
    """
    A confirm token plus the tool and argument digest of the call presenting
    it. The token must have been issued for exactly this tool and digest.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    token: str = Field(min_length=1, max_length=TOKEN_MAX)
    tool: ToolName
    args_sha256: Sha256Hex
