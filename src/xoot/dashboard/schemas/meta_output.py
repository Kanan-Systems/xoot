"""What GET /api/v1/meta returns."""

from pydantic import BaseModel, ConfigDict


class MetaOutput(BaseModel):
    """The running xoot version."""

    model_config = ConfigDict(frozen=True)

    version: str
