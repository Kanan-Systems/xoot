"""What `xoot workflow import` reports."""

from pydantic import BaseModel, ConfigDict

from xoot.models.workflow.workflow_plan import WorkflowPlan


class WorkflowImportOutput(BaseModel):
    """The project, the workflow version now active, and what the import changed."""

    model_config = ConfigDict(frozen=True)

    project: str
    version: int
    plan: WorkflowPlan
