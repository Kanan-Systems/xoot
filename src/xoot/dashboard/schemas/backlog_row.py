"""A backlog item as the dashboard lists it."""

from pydantic import ConfigDict

from xoot.server.schemas.backlog_entry import BacklogEntry


class BacklogRow(BacklogEntry):
    """
    The backlog entry plus when the item was created and why it was
    captured: the first line of its body, cut to WHY_MAX characters.
    """

    model_config = ConfigDict(frozen=True)

    created_at: str
    why: str
