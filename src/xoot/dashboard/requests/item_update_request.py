"""PATCH /api/v1/projects/{p}/items/{key}."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from xoot.dashboard.requests.fields import Token
from xoot.models.fields import Body, Id, StateName, Title, reject_explicit_none

CHANGES = ("title", "body", "state")


class ItemUpdateRequest(BaseModel):
    """
    New title, body or state, based on expected_version. Dropping an item that
    has children first returns a preview and a confirm_token; send the state
    alone, then the same body plus the token.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    expected_version: Id
    title: Title | None = None
    body: Body | None = None
    state: StateName | None = None
    confirm_token: Token | None = None

    @model_validator(mode="after")
    def _some_change(self) -> Self:
        """Require at least one change and refuse explicit nulls."""
        reject_explicit_none(self, CHANGES)
        if not self.model_fields_set & set(CHANGES):
            raise ValueError("send at least one of title, body or state")
        return self
