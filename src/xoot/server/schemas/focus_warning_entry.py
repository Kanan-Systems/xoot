"""A focus item another open session also works on."""

from pydantic import BaseModel, ConfigDict


class FocusWarningEntry(BaseModel):
    """The focus item and the other open sessions it is linked to."""

    model_config = ConfigDict(frozen=True)

    key: str
    open_sessions: list[str]
