"""GET /api/v1/projects/{p}/backlog."""

from pydantic import BaseModel, ConfigDict

from xoot.dashboard.schemas.backlog_row import BacklogRow


class BacklogView(BaseModel):
    """
    Open backlog items of every level, project level first, then by key;
    truncated when the cap hid items.
    """

    model_config = ConfigDict(frozen=True)

    project: str
    items: list[BacklogRow]
    truncated: bool
