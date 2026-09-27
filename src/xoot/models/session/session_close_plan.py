"""The planned effect of closing a session."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id
from xoot.models.item.item_change import ItemChange
from xoot.models.session.close_warning import CloseWarning
from xoot.models.session.disposition import Disposition


class SessionClosePlan(BaseModel):
    """
    required_item_ids are the linked items that need a disposition;
    missing_item_ids are those the request left out (close refuses while
    any are missing). changes come from dispositions; auto_backlog moves
    stale session-backlog items to the project backlog. warnings flag items
    left live under a backlogged or dropped parent; they never block.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: Id
    required_item_ids: tuple[Id, ...]
    missing_item_ids: tuple[Id, ...]
    dispositions: dict[Id, Disposition]
    changes: tuple[ItemChange, ...]
    auto_backlog: tuple[ItemChange, ...]
    warnings: tuple[CloseWarning, ...] = ()
