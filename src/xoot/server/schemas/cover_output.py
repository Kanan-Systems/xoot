"""What backlog_cover returns."""

from xoot.server.schemas.completion_fields import CompletionFields
from xoot.server.schemas.item_detail import ItemDetail
from xoot.server.schemas.item_summary import ItemSummary


class CoverOutput(CompletionFields):
    """The new subtask, the backlog item it closed, and the engine's outcome."""

    project: str
    subtask: ItemDetail
    backlog: ItemSummary
