"""An open goal and how far its batches are."""

from pydantic import BaseModel, ConfigDict

from xoot.models.workflow.category import Category


class GoalProgressEntry(BaseModel):
    """
    batches_done of batches_total are done (dropped batches count in
    neither); open_backlog counts the open backlog anywhere in the goal.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    title: str
    state: str
    category: Category | None
    batches_done: int
    batches_total: int
    open_backlog: int
    version: int
