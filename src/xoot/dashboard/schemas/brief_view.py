"""What GET /api/v1/projects/{prefix}/brief returns."""

from pydantic import BaseModel, ConfigDict

from xoot.dashboard.schemas.project_info import ProjectInfo
from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.category import Category
from xoot.server.schemas.decision_summary import DecisionSummary
from xoot.server.schemas.item_summary import ItemSummary
from xoot.server.schemas.session_summary import SessionSummary
from xoot.server.schemas.workflow_entry import WorkflowEntry


class BriefView(BaseModel):
    """
    The brief_get picture without its MCP-only fields: counts, open
    sessions, work in flight, backlogs, recent decisions and the workflow.
    """

    model_config = ConfigDict(frozen=True)

    project: ProjectInfo
    workflow: dict[ItemKind, WorkflowEntry]
    counts: dict[Category, int]
    # Work in flight.
    active: list[ItemSummary]
    awaiting_input: list[ItemSummary]
    # Sessions and what they hold.
    open_sessions: list[SessionSummary]
    open_sessions_truncated: bool
    open_session_backlog: list[ItemSummary]
    open_session_backlog_truncated: bool
    # Backlogs left by closed sessions, and the project backlog.
    pending_session_backlog: list[ItemSummary]
    project_backlog_count: int
    recent_decisions: list[DecisionSummary]
