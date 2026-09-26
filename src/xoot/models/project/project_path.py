"""A stored project path row."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import AbsolutePath, Id


class ProjectPath(BaseModel):
    """An absolute, normalized directory that belongs to one project."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: AbsolutePath
    project_id: Id
