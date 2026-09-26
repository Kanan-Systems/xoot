"""A stored decision row."""

from xoot.models.decision.new_decision import NewDecision
from xoot.models.fields import Id, Timestamp


class Decision(NewDecision):
    """
    A recorded decision: the inserted columns plus the id, version and
    updated_at the database maintains. key is "<prefix>-D<number>". A newer
    decision can supersede it; scope_item_id optionally ties it to one item.
    """

    id: Id
    version: Id
    updated_at: Timestamp
