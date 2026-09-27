"""The capture op: park a side item in the session's backlog."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Body, Title


class CaptureOp(BaseModel):
    """An unfiled subtask in the session's backlog, as the capture tool makes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    op: Literal["capture"]
    title: Title
    body: Body = ""
