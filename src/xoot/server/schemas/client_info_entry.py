"""The client name and version sent at initialization."""

from pydantic import BaseModel, ConfigDict


class ClientInfoEntry(BaseModel):
    """Raw client_info as the client reported it; informational only."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
