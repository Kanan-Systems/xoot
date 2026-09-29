"""A goal or batch the completion engine left open because of open backlog."""

from pydantic import BaseModel, ConfigDict


class BlockedEntry(BaseModel):
    """
    Every child is done or dropped, but open_backlog backlog items still sit
    on it: cover them, resolve them (item_update to done) or push them up.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    open_backlog: int
