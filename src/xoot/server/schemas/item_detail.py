"""A single item with its body and every reference."""

from xoot.server.schemas.item_summary import ItemSummary


class ItemDetail(ItemSummary):
    """
    The summary plus the body, the awaited decision, the backlog links
    (found_on and covered_by on a backlog item, origin on a subtask made
    from one), every older key that still resolves to it, and timestamps.
    """

    body: str
    awaiting_decision: str | None
    found_on: str | None
    covered_by: str | None
    origin: str | None
    aliases: list[str]
    created_at: str
    updated_at: str
