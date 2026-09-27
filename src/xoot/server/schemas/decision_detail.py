"""A single decision with its body."""

from xoot.server.schemas.decision_summary import DecisionSummary


class DecisionDetail(DecisionSummary):
    """The summary plus the body and creation time."""

    body: str
    created_at: str
