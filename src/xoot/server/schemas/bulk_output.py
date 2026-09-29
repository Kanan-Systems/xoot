"""What items_create_bulk returns."""

from xoot.server.schemas.completion_fields import CompletionFields
from xoot.server.schemas.item_summary import ItemSummary
from xoot.server.schemas.literals import Phase
from xoot.server.schemas.planned_entry import PlannedEntry


class BulkOutput(CompletionFields):
    """
    A preview lists the planned items and a confirm_token; an apply lists
    the created items with the keys they actually got, and what the
    completion engine did (new subtasks reopen a done batch).
    """

    project: str
    phase: Phase
    confirm_token: str | None
    planned: list[PlannedEntry]
    created: list[ItemSummary]
