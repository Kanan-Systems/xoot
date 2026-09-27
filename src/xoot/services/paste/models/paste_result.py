"""Everything a paste block did, from a dry run or an apply."""

from pydantic import BaseModel, ConfigDict

from xoot.models.session.session_status import SessionStatus
from xoot.services.paste.models.paste_auto_backlog import PasteAutoBacklog
from xoot.services.paste.models.paste_decision_state import PasteDecisionState
from xoot.services.paste.models.paste_item_state import PasteItemState
from xoot.services.paste.models.paste_op_outcome import PasteOpOutcome


class PasteResult(BaseModel):
    """
    The per-op outcomes, the ref-to-key map, every touched item and decision
    as the block leaves it, the auto-backlog side effects, and the session.
    Holds keys, names and versions only, never titles or bodies. The apply
    commits only when its result digests the same as the dry run's.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    project: str
    session: str
    session_status: SessionStatus
    outcomes: tuple[PasteOpOutcome, ...]
    refs: dict[str, str]
    items: tuple[PasteItemState, ...]
    decisions: tuple[PasteDecisionState, ...]
    auto_backlog: tuple[PasteAutoBacklog, ...]
