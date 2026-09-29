"""The key-based changes of an item_update: the MCP tool's argument and a paste op's field."""

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.fields import Body, StateName, Title


class ItemChangesInput(BaseModel):
    """
    Fields to change; leave a field out to keep it. parent and
    awaiting_decision take keys; awaiting_decision takes null to clear.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Title | None = None
    body: Body | None = None
    state: StateName | None = Field(
        default=None, description="A state of the project's workflow."
    )
    parent: str | None = Field(
        default=None,
        description=(
            "New parent key: a goal for a batch, a batch for a subtask. Send "
            "it alone. Backlog items move with backlog_push."
        ),
    )
    awaiting_decision: str | None = Field(
        default=None, description="Decision key the item waits for, or null."
    )
