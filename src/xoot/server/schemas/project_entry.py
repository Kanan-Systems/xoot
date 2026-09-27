"""A registered project as tools report it."""

from pydantic import BaseModel, ConfigDict


class ProjectEntry(BaseModel):
    """
    The key prefix every key of the project starts with, its name, its
    aliases and the directories that resolve to it.
    """

    model_config = ConfigDict(frozen=True)

    key_prefix: str
    name: str
    aliases: list[str]
    paths: list[str]
