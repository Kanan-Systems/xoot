"""One item a bulk create preview plans."""

from pydantic import BaseModel, ConfigDict

from xoot.models.item.item_kind import ItemKind


class PlannedEntry(BaseModel):
    """The planned key, kind, title and parent key (existing or planned)."""

    model_config = ConfigDict(frozen=True)

    key: str
    kind: ItemKind
    title: str
    parent: str | None
