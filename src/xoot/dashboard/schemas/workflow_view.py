"""GET /api/v1/projects/{p}/workflow."""

from pydantic import BaseModel, ConfigDict

from xoot.dashboard.schemas.workflow_kind_view import WorkflowKindView
from xoot.models.item.item_kind import ItemKind


class WorkflowView(BaseModel):
    """
    The project's active workflow: every state of each item kind with its
    category, as brief_get shows it, plus the allowed moves of a kind that
    restricts them, so an editor offers only real states and real moves.
    """

    model_config = ConfigDict(frozen=True)

    workflow: dict[ItemKind, WorkflowKindView]
