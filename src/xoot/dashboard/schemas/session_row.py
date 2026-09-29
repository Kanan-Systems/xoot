"""A session as the sessions table lists it."""

from pydantic import ConfigDict

from xoot.server.schemas.session_summary import SessionSummary


class SessionRow(SessionSummary):
    """The session summary plus how many items it is linked to."""

    model_config = ConfigDict(frozen=True)

    linked_items: int
