"""One named state in a kind's workflow."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import StateName
from xoot.models.workflow.category import Category


class StateSpec(BaseModel):
    """A project-chosen state name and the fixed category it belongs to."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: StateName
    category: Category
