"""The decision_record op: record one decision."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Body, Title
from xoot.services.paste.models.fields import DecisionKeyOrRef, ItemKeyOrRef, RefName


class DecisionRecordOp(BaseModel):
    """
    A new decision on the goal, batch or subtask it was made on (owner, a
    key or item ref). status is locked or deferred, as in the
    decision_record tool. supersedes is a decision key or ref of the same
    goal, which becomes superseded.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    op: Literal["decision_record"]
    ref: RefName | None = None
    owner: ItemKeyOrRef
    title: Title
    body: Body
    status: Literal["locked", "deferred"]
    supersedes: DecisionKeyOrRef | None = None
