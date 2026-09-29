"""GET /api/v1/projects/{p}/brief."""

from pydantic import BaseModel, ConfigDict

from xoot.dashboard.schemas.project_info import ProjectInfo
from xoot.models.item.backlog_level import BacklogLevel
from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.category import Category
from xoot.server.schemas.blocked_entry import BlockedEntry
from xoot.server.schemas.decision_summary import DecisionSummary
from xoot.server.schemas.goal_progress_entry import GoalProgressEntry
from xoot.server.schemas.item_summary import ItemSummary
from xoot.server.schemas.workflow_entry import WorkflowEntry


class BriefView(BaseModel):
    """
    The brief_get picture without its MCP-only fields: counts, open goals
    with batch progress, work in flight, what open backlog blocks, open
    backlog per level, recent decisions and the workflow.
    """

    model_config = ConfigDict(frozen=True)

    project: ProjectInfo
    workflow: dict[ItemKind, WorkflowEntry]
    # Goals, and what open backlog holds open.
    open_goals: list[GoalProgressEntry]
    open_goals_truncated: bool
    blocked: list[BlockedEntry]
    backlog_counts: dict[BacklogLevel, int]
    # Work in flight.
    counts: dict[Category, int]
    active: list[ItemSummary]
    awaiting_input: list[ItemSummary]
    recent_decisions: list[DecisionSummary]
