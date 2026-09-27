"""What brief_get returns."""

from pydantic import BaseModel, ConfigDict

from xoot.models.workflow.category import Category
from xoot.server.schemas.decision_summary import DecisionSummary
from xoot.server.schemas.item_summary import ItemSummary
from xoot.server.schemas.literals import ResolvedBy
from xoot.server.schemas.project_entry import ProjectEntry
from xoot.server.schemas.session_summary import SessionSummary


class BriefOutput(BaseModel):
    """
    A project's current picture: counts, open sessions, what is in flight,
    what waits in backlogs and the latest decisions. Lists are capped.
    """

    model_config = ConfigDict(frozen=True)

    header: str
    project: ProjectEntry
    resolved_by: ResolvedBy
    db_path: str
    counts: dict[Category, int]
    open_sessions: list[SessionSummary]
    active: list[ItemSummary]
    awaiting_input: list[ItemSummary]
    pending_session_backlog: list[ItemSummary]
    project_backlog_count: int
    recent_decisions: list[DecisionSummary]
