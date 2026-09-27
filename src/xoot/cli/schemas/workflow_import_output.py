"""What `xoot workflow import` reports."""

from pydantic import BaseModel, ConfigDict

from xoot.models.workflow.workflow_plan import WorkflowPlan


class WorkflowImportOutput(BaseModel):
    """
    The project, the workflow version now active, and what the import
    changed. changed is False when the file matched the active workflow and
    nothing was written.
    """

    model_config = ConfigDict(frozen=True)

    project: str
    version: int
    changed: bool
    plan: WorkflowPlan
