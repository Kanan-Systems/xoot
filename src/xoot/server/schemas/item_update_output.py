"""What item_update returns."""

from xoot.server.schemas.affected_item_entry import AffectedItemEntry
from xoot.server.schemas.completion_fields import CompletionFields
from xoot.server.schemas.item_detail import ItemDetail
from xoot.server.schemas.literals import Phase, UpdateMode
from xoot.server.schemas.subtree_output import SubtreeOutput


class ItemUpdateOutput(CompletionFields):
    """
    mode is the path taken. A direct update returns the item. A drop or
    reparent of an item with children first returns a preview plan and a
    confirm_token, then the applied plan; an applied drop or reparent also
    returns every item it changed, as it now stands, in items. A reparent
    re-keys the moved subtree; the old keys keep resolving.
    """

    project: str
    mode: UpdateMode
    phase: Phase
    confirm_token: str | None
    item: ItemDetail | None
    items: list[AffectedItemEntry] | None = None
    plan: SubtreeOutput | None
