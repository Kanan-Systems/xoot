"""The capture op: record open work found along the way as a backlog item."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Body, Title
from xoot.services.paste.models.fields import ItemKeyOrRef, RefName


class CaptureOp(BaseModel):
    """
    A backlog item, placed as the capture tool places it: found_on is the
    item it was found on, the body the why. ref names it for later ops.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    op: Literal["capture"]
    ref: RefName | None = None
    found_on: ItemKeyOrRef
    title: Title
    body: Body = ""
