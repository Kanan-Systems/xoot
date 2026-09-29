"""A stored decision row."""

from xoot.models.decision.new_decision import NewDecision
from xoot.models.fields import Id, Timestamp


class Decision(NewDecision):
    """
    A recorded decision: the inserted columns plus the id, version and
    updated_at the database maintains. key is "<owner key>/decision-<n>",
    derived on read from the owner's current key, so it follows the owner
    when the owner moves. A newer decision on the same goal can supersede it.
    """

    id: Id
    key: str
    version: Id
    updated_at: Timestamp
