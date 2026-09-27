"""The session_start op: open the block's session."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.fields import Title
from xoot.models.session.session_start import MAX_FOCUS_ITEMS
from xoot.services.paste.models.fields import KeyOrRef


class SessionStartOp(BaseModel):
    """
    Starts a session of the block's project, recorded with client paste.
    Allowed only as the first op; focus names existing item keys.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    op: Literal["session_start"]
    title: Title
    focus: list[KeyOrRef] = Field(default_factory=list, max_length=MAX_FOCUS_ITEMS)
