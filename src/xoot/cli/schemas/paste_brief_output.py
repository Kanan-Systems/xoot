"""What `xoot paste brief` produces."""

from pydantic import BaseModel, ConfigDict


class PasteBriefOutput(BaseModel):
    """
    The markdown brief for a chat, its size in UTF-8 bytes, and what was
    left out to keep it within the size limit.
    """

    model_config = ConfigDict(frozen=True)

    project: str
    markdown: str
    size_bytes: int
    cut_items: int
    cut_decisions: int
