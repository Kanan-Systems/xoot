"""A project together with the names and directories that resolve to it."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import ProjectDir, Slug
from xoot.models.project.project import Project


class ProjectOverview(BaseModel):
    """A stored project, its aliases by name and its paths in order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project: Project
    aliases: tuple[Slug, ...]
    paths: tuple[ProjectDir, ...]
