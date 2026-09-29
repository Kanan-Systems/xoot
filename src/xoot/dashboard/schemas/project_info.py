"""A project as the dashboard's project switcher shows it."""

from pydantic import BaseModel, ConfigDict


class ProjectInfo(BaseModel):
    """
    The key prefix the URLs use, the display name and the aliases.
    Registered paths are left out: the browser has no use for local paths.
    """

    model_config = ConfigDict(frozen=True)

    key_prefix: str
    name: str
    aliases: list[str]
