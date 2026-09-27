"""What session_start returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.client_info_entry import ClientInfoEntry
from xoot.server.schemas.focus_warning_entry import FocusWarningEntry
from xoot.server.schemas.item_summary import ItemSummary
from xoot.server.schemas.literals import ResolvedBy
from xoot.server.schemas.session_summary import SessionSummary


class SessionStartOutput(BaseModel):
    """
    The new session, the client it was recorded with, backlog items left by
    closed sessions, and focus items other open sessions share.
    """

    model_config = ConfigDict(frozen=True)

    project: str
    resolved_by: ResolvedBy
    session: SessionSummary
    client_info: ClientInfoEntry | None
    pending: list[ItemSummary]
    warnings: list[FocusWarningEntry]
