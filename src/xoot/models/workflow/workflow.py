"""A stored workflow version row."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Id, Timestamp
from xoot.models.workflow.workflow_definition import WorkflowDefinition


class Workflow(BaseModel):
    """
    One immutable version of a project's workflow. Changing a workflow adds
    a version and points the project at it; old versions stay for audit.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Id
    project_id: Id
    version: Id
    definition: WorkflowDefinition
    created_at: Timestamp
