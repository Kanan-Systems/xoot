"""What brief_get returns."""

from pydantic import BaseModel, ConfigDict

from xoot.models.item.backlog_level import BacklogLevel
from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.category import Category
from xoot.server.schemas.blocked_entry import BlockedEntry
from xoot.server.schemas.decision_summary import DecisionSummary
from xoot.server.schemas.goal_progress_entry import GoalProgressEntry
from xoot.server.schemas.item_summary import ItemSummary
from xoot.server.schemas.literals import ResolvedBy
from xoot.server.schemas.project_entry import ProjectEntry
from xoot.server.schemas.workflow_entry import WorkflowEntry


class BriefOutput(BaseModel):
    """
    A project's current picture: open goals with batch progress, what is in
    flight, what open backlog blocks, open backlog per level, the latest
    decisions, and the active workflow per item kind, whose state names are
    the only ones item_update accepts. Lists are capped; the truncated flag
    says more goals are open than are listed. db_path is None where the
    path is not shown (the dashboard).
    """

    model_config = ConfigDict(frozen=True)

    header: str
    project: ProjectEntry
    resolved_by: ResolvedBy
    db_path: str | None
    counts: dict[Category, int]
    open_goals: list[GoalProgressEntry]
    open_goals_truncated: bool
    active: list[ItemSummary]
    awaiting_input: list[ItemSummary]
    blocked: list[BlockedEntry]
    backlog_counts: dict[BacklogLevel, int]
    recent_decisions: list[DecisionSummary]
    workflow: dict[ItemKind, WorkflowEntry]
