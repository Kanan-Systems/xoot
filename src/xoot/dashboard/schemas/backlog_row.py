"""An item as the backlog tables list it."""

from pydantic import ConfigDict

from xoot.server.schemas.item_summary import ItemSummary


class BacklogRow(ItemSummary):
    """The item summary plus when the item was created."""

    model_config = ConfigDict(frozen=True)

    created_at: str
