"""One open session and the items its backlog holds."""

from pydantic import BaseModel, ConfigDict

from xoot.models.item.item import Item
from xoot.models.session.session import Session


class SessionBacklog(BaseModel):
    """
    An open session with the items parked in its backlog. Other clients'
    briefs cannot see these until the session closes, so views list them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    session: Session
    items: tuple[Item, ...]
