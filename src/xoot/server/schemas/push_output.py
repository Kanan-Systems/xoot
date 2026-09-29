"""What backlog_push returns."""

from xoot.server.schemas.affected_item_entry import AffectedItemEntry
from xoot.server.schemas.completion_fields import CompletionFields
from xoot.server.schemas.literals import Phase
from xoot.server.schemas.subtree_output import SubtreeOutput


class PushOutput(CompletionFields):
    """
    A preview returns the plan (the new key) and a confirm_token; an apply
    returns the plan written, the item as it now stands, and the engine's
    outcome. The old key keeps resolving to the item.
    """

    project: str
    phase: Phase
    confirm_token: str | None
    plan: SubtreeOutput
    item: AffectedItemEntry | None
