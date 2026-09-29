"""One item as a previewed plan leaves it, the unit a plan digest covers."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Sha256Hex, StateName, Title
from xoot.models.item.item_kind import ItemKind


class PlanEntry(BaseModel):
    """
    Every column an apply can write to one item, in its post-apply form.
    References are public keys rather than ids, so a preview and its apply
    agree on them without depending on row ids; the body is represented by
    its digest. A move changes key and parent_key, so both are pinned.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    kind: ItemKind
    title: Title
    body_sha256: Sha256Hex
    state: StateName
    parent_key: str | None
    awaiting_decision_key: str | None
