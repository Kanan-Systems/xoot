"""A registered project as tools report it."""

from pydantic import BaseModel, ConfigDict


class ProjectEntry(BaseModel):
    """The key prefix every key of the project starts with, its name and aliases."""

    model_config = ConfigDict(frozen=True)

    key_prefix: str
    name: str
    aliases: list[str]
