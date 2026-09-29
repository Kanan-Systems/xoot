"""The receipt `xoot paste apply` prints after a successful apply."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from xoot.models.item.blocked_item import BlockedItem
from xoot.services.paste.models.paste_decision_state import PasteDecisionState
from xoot.services.paste.models.paste_item_state import PasteItemState


class PasteReceipt(BaseModel):
    """
    What the user pastes back into the chat: the key each ref became, the
    version and state of every record the block wrote (goals and batches the
    completion engine changed included), so the next block can pass correct
    expected_versions, and what completed, reopened or stays
    blocked by open backlog. Never titles or bodies.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    xoot: Literal[2] = 2
    project: str
    refs: dict[str, str]
    items: list[PasteItemState]
    decisions: list[PasteDecisionState]
    completed: list[str]
    reopened: list[str]
    blocked: list[BlockedItem]
