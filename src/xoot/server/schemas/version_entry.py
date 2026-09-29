"""One item whose version a write changed."""

from pydantic import BaseModel, ConfigDict


class VersionEntry(BaseModel):
    """The item's key, new version and state, for the next expected_version."""

    model_config = ConfigDict(frozen=True)

    key: str
    version: int
    state: str
