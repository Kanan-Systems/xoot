"""A stored project row."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id, KeyPrefix, Timestamp, Title


class Project(BaseModel):
    """
    A registered project: its key prefix, number counters and active
    workflow. Item and decision keys are derived from key_prefix. next_seq
    orders session starts and closes, independent of the clock.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Id
    key_prefix: KeyPrefix
    name: Title
    next_item_number: Id
    next_decision_number: Id
    next_seq: Id
    active_workflow_id: Id | None
    created_at: Timestamp
