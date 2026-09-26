"""A stored project alias row."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id, Slug


class ProjectAlias(BaseModel):
    """A globally unique short name that resolves to one project."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alias: Slug
    project_id: Id
