"""The session_close op: close the block's session."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.fields import Body
from xoot.models.session.disposition import Disposition
from xoot.models.session.session_close import MAX_DISPOSITIONS
from xoot.services.paste.models.fields import KeyOrRef


class SessionCloseOp(BaseModel):
    """
    Closes the session: one disposition per open linked item, keyed by item
    key or item ref. Allowed only as the last op.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    op: Literal["session_close"]
    dispositions: dict[KeyOrRef, Disposition] = Field(
        default_factory=dict, max_length=MAX_DISPOSITIONS
    )
    summary: Body | None = None
