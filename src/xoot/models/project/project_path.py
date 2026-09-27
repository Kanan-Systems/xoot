"""A stored project path row."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id, ProjectDir


class ProjectPath(BaseModel):
    """An absolute, normalized directory other than "/" that belongs to one project."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: ProjectDir
    project_id: Id
