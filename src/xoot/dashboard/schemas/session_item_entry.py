"""One item linked to a session, as the session detail shows it."""

from pydantic import BaseModel, ConfigDict

from xoot.models.session.disposition import Disposition
from xoot.server.schemas.item_summary import ItemSummary


class SessionItemEntry(BaseModel):
    """
    The item as it is now, the disposition the session's close gave it
    (None while the session is open, or when the item was no longer open at
    close), and whether the session captured it.
    """

    model_config = ConfigDict(frozen=True)

    item: ItemSummary
    disposition: Disposition | None
    captured: bool
