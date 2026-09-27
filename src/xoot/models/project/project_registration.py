"""Input for registering a project."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from xoot.models.fields import KeyPrefix, ProjectDir, Slug, Title

MAX_NAMES = 16


class ProjectRegistration(BaseModel):
    """A new project with its key prefix, optional aliases and paths."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key_prefix: KeyPrefix
    name: Title
    aliases: tuple[Slug, ...] = Field(default=(), max_length=MAX_NAMES)
    paths: tuple[ProjectDir, ...] = Field(default=(), max_length=MAX_NAMES)

    @model_validator(mode="after")
    def _unique_names(self) -> Self:
        """Reject repeated aliases or paths (compared after normalization)."""
        if len(set(self.aliases)) != len(self.aliases):
            raise ValueError("aliases must be unique")
        if len(set(self.paths)) != len(self.paths):
            raise ValueError("paths must be unique")
        return self
