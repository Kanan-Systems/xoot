"""Input for capturing a quick note as an unfiled subtask."""

from pydantic import BaseModel, ConfigDict

from xoot.models.fields import Body, Title


class ItemDraft(BaseModel):
    """Just a title and an optional body; capture decides everything else."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Title
    body: Body = ""
