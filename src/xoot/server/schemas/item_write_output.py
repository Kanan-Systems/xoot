"""What item_create and capture return."""

from xoot.server.schemas.completion_fields import CompletionFields
from xoot.server.schemas.item_detail import ItemDetail


class ItemWriteOutput(CompletionFields):
    """The new item, and what the completion engine did."""

    project: str
    item: ItemDetail
