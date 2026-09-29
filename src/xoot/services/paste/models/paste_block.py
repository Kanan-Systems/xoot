"""The whole xoot block: a protocol version, a project and ops."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints

from xoot.services.paste.models.backlog_cover_op import BacklogCoverOp
from xoot.services.paste.models.backlog_push_op import BacklogPushOp
from xoot.services.paste.models.capture_op import CaptureOp
from xoot.services.paste.models.decision_record_op import DecisionRecordOp
from xoot.services.paste.models.decision_update_op import DecisionUpdateOp
from xoot.services.paste.models.item_create_op import ItemCreateOp
from xoot.services.paste.models.item_update_op import ItemUpdateOp

MAX_OPS = 100
# 2 since xoot 0.3: the goal model, with nested keys.
PROTOCOL_VERSION = 2

type PasteOp = Annotated[
    ItemCreateOp
    | ItemUpdateOp
    | CaptureOp
    | BacklogCoverOp
    | BacklogPushOp
    | DecisionRecordOp
    | DecisionUpdateOp,
    Field(discriminator="op"),
]

OP_NAMES = frozenset(
    {
        "item_create", "item_update", "capture", "backlog_cover",
        "backlog_push", "decision_record", "decision_update",
    }
)  # fmt: skip


class PasteBlock(BaseModel):
    """
    One block as pasted. xoot is the protocol version and must be 2 (a
    strict integer: not true, 2.0 or "2"). project is the alias or key
    prefix every op works in.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    xoot: Annotated[StrictInt, Field(ge=PROTOCOL_VERSION, le=PROTOCOL_VERSION)]
    project: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    ops: list[PasteOp] = Field(min_length=1, max_length=MAX_OPS)
