"""A stored project row."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id, KeyPrefix, Timestamp, Title


class Project(BaseModel):
    """
    A registered project: its key prefix, the counters for the items that
    sit directly on it (goals and the project backlog) and its active
    workflow. Keys qualify as "<key_prefix>:<key>".
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Id
    key_prefix: KeyPrefix
    name: Title
    next_goal_number: Id
    next_backlog_number: Id
    active_workflow_id: Id | None
    created_at: Timestamp
