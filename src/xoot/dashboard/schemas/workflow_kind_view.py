"""One item kind's workflow, as GET /workflow shows it."""

from pydantic import BaseModel, ConfigDict

from xoot.models.workflow.state_spec import StateSpec


class WorkflowKindView(BaseModel):
    """
    Every state of one kind with its category, in workflow order, and the
    moves a user may make. transitions is null when any state may move to
    any other; when the kind restricts them it maps every state name to the
    states it may move to (possibly none). Keeping the current state is
    always allowed and is not listed.
    """

    model_config = ConfigDict(frozen=True)

    states: list[StateSpec]
    transitions_restricted: bool
    transitions: dict[str, list[str]] | None
