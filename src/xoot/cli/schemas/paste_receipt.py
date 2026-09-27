"""The receipt `xoot paste apply` prints after a successful apply."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from xoot.models.session.session_status import SessionStatus
from xoot.services.paste.models.paste_decision_state import PasteDecisionState
from xoot.services.paste.models.paste_item_state import PasteItemState


class PasteReceipt(BaseModel):
    """
    What the user pastes back into the chat: the session, the key each ref
    became, and the version and state of every touched record, so the next
    block can pass correct expected_versions. Never titles or bodies.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    xoot: Literal[1] = 1
    project: str
    session: str
    session_status: SessionStatus
    refs: dict[str, str]
    items: list[PasteItemState]
    decisions: list[PasteDecisionState]
