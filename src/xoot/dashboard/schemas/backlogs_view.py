"""What GET /api/v1/projects/{prefix}/backlogs returns."""

from pydantic import BaseModel, ConfigDict

from xoot.dashboard.schemas.backlog_row import BacklogRow
from xoot.dashboard.schemas.session_backlog_entry import SessionBacklogEntry


class BacklogsView(BaseModel):
    """
    Each open session's backlog, the project backlog and the unfiled
    subtasks. A capture shows under its session and under unfiled.
    """

    model_config = ConfigDict(frozen=True)

    project: str
    sessions: list[SessionBacklogEntry]
    project_backlog: list[BacklogRow]
    project_backlog_truncated: bool
    unfiled: list[BacklogRow]
    unfiled_truncated: bool
