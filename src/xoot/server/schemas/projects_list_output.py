"""What projects_list returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.project_entry import ProjectEntry


class ProjectsListOutput(BaseModel):
    """Every registered project and the database file the server uses."""

    model_config = ConfigDict(frozen=True)

    db_path: str
    projects: list[ProjectEntry]
