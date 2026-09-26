"""A non-blocking warning returned by session start."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id


class FocusWarning(BaseModel):
    """A focus item that other open sessions are also linked to."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: Id
    key: str
    open_session_ids: tuple[Id, ...]
