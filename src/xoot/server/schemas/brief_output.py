"""What brief_get returns."""

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.category import Category
from xoot.server.schemas.decision_summary import DecisionSummary
from xoot.server.schemas.item_summary import ItemSummary
from xoot.server.schemas.literals import ResolvedBy
from xoot.server.schemas.project_entry import ProjectEntry
from xoot.server.schemas.session_summary import SessionSummary
from xoot.server.schemas.workflow_entry import WorkflowEntry


class BriefOutput(BaseModel):
    """
    A project's current picture: counts, open sessions, what is in flight,
    what waits in backlogs and the latest decisions. Lists are capped;
    open_sessions_truncated says more sessions are open than are listed.
    workflow is the active workflow per item kind, whose state names are the
    only ones item_update accepts. open_session_backlog lists what open
    sessions have parked, which pending_session_backlog (closed sessions
    only) leaves out.
    """

    model_config = ConfigDict(frozen=True)

    header: str
    project: ProjectEntry
    resolved_by: ResolvedBy
    db_path: str
    counts: dict[Category, int]
    open_sessions: list[SessionSummary]
    open_sessions_truncated: bool
    active: list[ItemSummary]
    awaiting_input: list[ItemSummary]
    pending_session_backlog: list[ItemSummary]
    project_backlog_count: int
    # Defaulted, so the field is additive for every existing producer.
    open_session_backlog: list[ItemSummary] = Field(default_factory=list)
    open_session_backlog_truncated: bool = False
    recent_decisions: list[DecisionSummary]
    workflow: dict[ItemKind, WorkflowEntry]
