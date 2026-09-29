"""Everything a paste block did, from a dry run or an apply."""

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.item.blocked_item import BlockedItem
from xoot.services.paste.models.paste_decision_state import PasteDecisionState
from xoot.services.paste.models.paste_encoding_warning import (
    PasteEncodingWarning,
)
from xoot.services.paste.models.paste_item_state import PasteItemState
from xoot.services.paste.models.paste_label import PasteLabel
from xoot.services.paste.models.paste_op_outcome import PasteOpOutcome


class PasteResult(BaseModel):
    """
    The per-op outcomes, the ref-to-key map, every touched item and decision
    as the block leaves it, and what the completion engine did: the goals
    and batches completed, reopened, or held open by open backlog. The apply
    commits only when its result digests the same as the dry run's.

    labels holds the kind and title of every touched record for the plan on
    the terminal. It is excluded from every dump, so the digest, --json
    output and the receipt hold keys, names and versions only, never titles.

    warnings names the fields of the block that look damaged by a clipboard
    code page. The CLI attaches them after the apply for --json; the digest
    leaves them out, since they describe the paste, not the database.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    project: str
    outcomes: tuple[PasteOpOutcome, ...]
    refs: dict[str, str]
    items: tuple[PasteItemState, ...]
    decisions: tuple[PasteDecisionState, ...]
    completed: tuple[str, ...] = ()
    reopened: tuple[str, ...] = ()
    blocked: tuple[BlockedItem, ...] = ()
    labels: dict[str, PasteLabel] = Field(default_factory=dict, exclude=True)
    warnings: tuple[PasteEncodingWarning, ...] = ()
