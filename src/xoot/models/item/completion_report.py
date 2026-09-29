"""What the completion engine did during one write."""

from pydantic import BaseModel, ConfigDict

from xoot.models.item.blocked_item import BlockedItem
from xoot.models.item.item_version import ItemVersion


class CompletionReport(BaseModel):
    """
    The keys the engine completed and reopened, the goals and batches it
    left open only because of open backlog, and every item whose version the
    write changed (the engine's own writes included). Every write result
    carries one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    completed: tuple[str, ...] = ()
    reopened: tuple[str, ...] = ()
    blocked: tuple[BlockedItem, ...] = ()
    changed: tuple[ItemVersion, ...] = ()
