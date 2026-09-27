"""A side effect of closing a session: a stale session backlog retired."""

from pydantic import BaseModel, ConfigDict


class PasteAutoBacklog(BaseModel):
    """
    An item xoot moves from the backlog of an earlier, closed session to the
    project backlog when the block's session closes. The move is recorded
    as the system's, not the paste's.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    origin_session: str | None
