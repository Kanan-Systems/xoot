"""The whole xoot block: a protocol version, a project, a session and ops."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints

from xoot.services.paste.models.capture_op import CaptureOp
from xoot.services.paste.models.decision_record_op import DecisionRecordOp
from xoot.services.paste.models.decision_update_op import DecisionUpdateOp
from xoot.services.paste.models.fields import KeyOrRef
from xoot.services.paste.models.item_create_op import ItemCreateOp
from xoot.services.paste.models.item_update_op import ItemUpdateOp
from xoot.services.paste.models.session_close_op import SessionCloseOp
from xoot.services.paste.models.session_start_op import SessionStartOp

MAX_OPS = 100
PROTOCOL_VERSION = 1

type PasteOp = Annotated[
    SessionStartOp
    | CaptureOp
    | ItemCreateOp
    | ItemUpdateOp
    | DecisionRecordOp
    | DecisionUpdateOp
    | SessionCloseOp,
    Field(discriminator="op"),
]

OP_NAMES = frozenset(
    {
        "session_start", "capture", "item_create", "item_update",
        "decision_record", "decision_update", "session_close",
    }
)  # fmt: skip


class PasteBlock(BaseModel):
    """
    One block as pasted. xoot is the protocol version and must be 1 (a
    strict integer: not true, 1.0 or "1"). The session is either named by
    "session" or started by a first session_start op, never both.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    xoot: Annotated[StrictInt, Field(ge=PROTOCOL_VERSION, le=PROTOCOL_VERSION)]
    project: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    session: KeyOrRef | None = None
    ops: list[PasteOp] = Field(min_length=1, max_length=MAX_OPS)
