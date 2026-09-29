"""The completion outcome every write result carries."""

from pydantic import BaseModel, ConfigDict, Field

from xoot.server.schemas.blocked_entry import BlockedEntry
from xoot.server.schemas.version_entry import VersionEntry


class CompletionFields(BaseModel):
    """
    What the completion engine did during the write: goals and batches it
    completed (done, or dropped when every child was dropped) and reopened,
    and those it left open only because of open backlog. changed lists every
    item whose version the call changed, the engine's goals and batches
    included, with its new version and state.
    """

    model_config = ConfigDict(frozen=True)

    completed: list[str] = Field(default_factory=list)
    reopened: list[str] = Field(default_factory=list)
    blocked: list[BlockedEntry] = Field(default_factory=list)
    changed: list[VersionEntry] = Field(default_factory=list)
