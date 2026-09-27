"""The decision_record op: record one decision."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Body, Title
from xoot.services.paste.models.fields import KeyOrRef, RefName


class DecisionRecordOp(BaseModel):
    """
    A new decision. status is locked or deferred, as in the
    decision_record tool: superseded is reached only by a newer decision.
    scope is an item key or item ref; supersedes is a decision key or
    decision ref, which becomes superseded.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    op: Literal["decision_record"]
    ref: RefName | None = None
    title: Title
    body: Body
    status: Literal["locked", "deferred"]
    scope: KeyOrRef | None = None
    supersedes: KeyOrRef | None = None
