"""What GET /api/v1/projects returns."""

from pydantic import BaseModel, ConfigDict

from xoot.dashboard.schemas.project_info import ProjectInfo


class ProjectsOutput(BaseModel):
    """Every registered project, by key prefix."""

    model_config = ConfigDict(frozen=True)

    projects: list[ProjectInfo]
