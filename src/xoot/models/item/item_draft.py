"""Input for capturing a backlog item."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Body, Title


class ItemDraft(BaseModel):
    """A title and a body saying why; capture decides where it sits."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Title
    body: Body = ""
