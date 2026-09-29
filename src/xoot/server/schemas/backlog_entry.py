"""A backlog item as backlog_list shows it."""

from xoot.models.item.backlog_level import BacklogLevel
from xoot.server.schemas.item_summary import ItemSummary


class BacklogEntry(ItemSummary):
    """The summary, where the item sits, and the item it was found on."""

    level: BacklogLevel
    found_on: str | None
