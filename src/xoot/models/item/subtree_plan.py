"""The planned effect of a subtree drop, a reparent or a backlog push."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id, Sha256Hex
from xoot.models.item.item_change import ItemChange


class SubtreePlan(BaseModel):
    """
    changes lists every row that will be written, in write order: a move
    lists the root first, then each descendant whose key changes with it; a
    drop lists the deepest items first and the root last. plan_sha256 digests the
    post-apply entry of every affected item, so an apply can tell whether
    the plan still matches its preview.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    root_id: Id
    changes: tuple[ItemChange, ...]
    plan_sha256: Sha256Hex
