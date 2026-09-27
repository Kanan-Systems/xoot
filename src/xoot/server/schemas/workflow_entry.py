"""One item kind's workflow, as brief_get shows it."""

from pydantic import BaseModel, ConfigDict

from xoot.models.workflow.state_spec import StateSpec


class WorkflowEntry(BaseModel):
    """
    Every state of one kind with its category, so a client picks real state
    names, and whether only listed transitions are allowed.
    """

    model_config = ConfigDict(frozen=True)

    states: list[StateSpec]
    transitions_restricted: bool
