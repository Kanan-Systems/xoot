"""What session_close returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.close_preview import ClosePreview
from xoot.server.schemas.literals import Phase
from xoot.server.schemas.session_summary import SessionSummary


class SessionCloseOutput(BaseModel):
    """A preview with its confirm_token, or the closed session."""

    model_config = ConfigDict(frozen=True)

    phase: Phase
    confirm_token: str | None
    preview: ClosePreview | None
    session: SessionSummary | None
