"""What starting a session returns."""

from pydantic import BaseModel, ConfigDict

from xoot.models.item.item import Item
from xoot.models.session.focus_warning import FocusWarning
from xoot.models.session.session import Session


class SessionStartResult(BaseModel):
    """
    The new session, session-backlog items left by closed sessions of the
    project, and warnings for focus items shared with other open sessions.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    session: Session
    pending: tuple[Item, ...]
    warnings: tuple[FocusWarning, ...]
