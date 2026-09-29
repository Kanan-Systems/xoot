"""The query of an endpoint that takes no parameters."""

from pydantic import BaseModel, ConfigDict


class NoParams(BaseModel):
    """Accepts nothing, so a stray parameter is refused, not ignored."""

    model_config = ConfigDict(frozen=True, extra="forbid")
