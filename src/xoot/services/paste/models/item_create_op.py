"""The item_create op: create one goal, batch or subtask."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Body, Title
from xoot.models.item.item_kind import ItemKind
from xoot.services.paste.models.fields import KeyOrRef, RefName


class ItemCreateOp(BaseModel):
    """
    A new item. ref names it for later ops; parent is an item key or the
    ref of an item created earlier in the block.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    op: Literal["item_create"]
    ref: RefName | None = None
    kind: ItemKind
    title: Title
    body: Body = ""
    parent: KeyOrRef | None = None
