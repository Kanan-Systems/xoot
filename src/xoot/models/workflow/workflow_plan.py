"""What replacing a project's workflow would do, shown before it is done."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import StateName
from xoot.models.item.item_kind import ItemKind


class WorkflowPlan(BaseModel):
    """
    Per item kind: the states the new definition removes, and how many
    items the change would rewrite (a remapped state or a dropped session
    backlog). Every kind appears in both maps, with () or 0 when unaffected.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    removed: dict[ItemKind, tuple[StateName, ...]]
    remaps: dict[ItemKind, int]
