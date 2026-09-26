"""Input for a partial item update."""

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, model_validator

from xoot.models.fields import (
    Body,
    Id,
    StateName,
    Title,
    provided_fields,
    reject_explicit_none,
)


class ItemUpdate(BaseModel):
    """
    Only fields the caller sets are changed. The nullable references can be
    cleared by setting them to None; title, body and state cannot. Parent
    changes go through the subtree reparent preview/apply instead.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Title | None = None
    body: Body | None = None
    state: StateName | None = None
    backlog_session_id: Id | None = None
    awaiting_decision_id: Id | None = None

    @model_validator(mode="after")
    def _no_clearing_required(self) -> Self:
        """Reject an explicit None for fields that cannot be cleared."""
        reject_explicit_none(self, ("title", "body", "state"))
        return self

    def provided(self) -> dict[str, Any]:
        """
        Return the fields the caller explicitly set.

        Returns:
            - fields (dict[str, Any]): field name to requested value.
        """
        return provided_fields(self)
