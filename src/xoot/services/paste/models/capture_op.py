"""The capture op: park a side item in the session's backlog."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Body, Title
from xoot.services.paste.models.fields import RefName


class CaptureOp(BaseModel):
    """
    An unfiled subtask in the session's backlog, as the capture tool makes.
    ref names it for later ops, such as a session_close disposition.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    op: Literal["capture"]
    ref: RefName | None = None
    title: Title
    body: Body = ""
