"""What `xoot workflow export` reports."""

from pydantic import BaseModel, ConfigDict

from xoot.models.workflow.workflow_definition import WorkflowDefinition


class WorkflowExportOutput(BaseModel):
    """The project, its active workflow version and definition, and the file written, if any."""

    model_config = ConfigDict(frozen=True)

    project: str
    version: int
    definition: WorkflowDefinition
    written_to: str | None
