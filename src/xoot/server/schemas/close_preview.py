"""The planned effect of closing a session."""

from pydantic import BaseModel, ConfigDict

from xoot.models.session.disposition import Disposition
from xoot.server.schemas.change_entry import ChangeEntry
from xoot.server.schemas.close_warning_entry import CloseWarningEntry


class ClosePreview(BaseModel):
    """
    required lists the linked items that need a disposition; missing, those
    still without one (no confirm_token is issued while any are missing).
    """

    model_config = ConfigDict(frozen=True)

    required: list[str]
    missing: list[str]
    dispositions: dict[str, Disposition]
    changes: list[ChangeEntry]
    auto_backlog: list[ChangeEntry]
    warnings: list[CloseWarningEntry]
