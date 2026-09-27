"""A single item with its body and every reference."""

from xoot.server.schemas.item_summary import ItemSummary


class ItemDetail(ItemSummary):
    """The summary plus the body, the awaited decision and timestamps."""

    body: str
    awaiting_decision: str | None
    unfiled: bool
    created_at: str
    updated_at: str
