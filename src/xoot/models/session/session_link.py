"""An item a session is linked to, with what the session did to it."""

from pydantic import BaseModel, ConfigDict

from xoot.models.item.item import Item
from xoot.models.session.disposition import Disposition


class SessionLink(BaseModel):
    """
    One linked item: its disposition once the session closed (None while
    open, or when the item was no longer open at close) and whether the
    session captured it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    item: Item
    disposition: Disposition | None
    captured: bool
