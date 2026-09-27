"""The changes argument of item_update."""

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.fields import Body, StateName, Title


class ItemChangesInput(BaseModel):
    """
    Fields to change; leave a field out to keep it. parent, backlog_session
    and awaiting_decision take keys, or null to clear.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Title | None = None
    body: Body | None = None
    state: StateName | None = Field(
        default=None, description="A state of the project's workflow."
    )
    parent: str | None = Field(
        default=None,
        description="New parent item key; null unfiles a subtask. Send it alone.",
    )
    backlog_session: str | None = Field(
        default=None, description="Session key whose backlog holds the item, or null."
    )
    awaiting_decision: str | None = Field(
        default=None, description="Decision key the item waits for, or null."
    )
