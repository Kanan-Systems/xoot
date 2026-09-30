"""PATCH /api/v1/projects/{p}."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from xoot.models.fields import Alias, Title


class ProjectRenameRequest(BaseModel):
    """
    A new display name, an extra alias, or both. The key prefix never
    changes: keys and URLs are built from it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Title | None = None
    alias: Alias | None = None

    @model_validator(mode="after")
    def _some_change(self) -> Self:
        """Require a name or an alias."""
        if self.name is None and self.alias is None:
            raise ValueError("send a name, an alias or both")
        return self
