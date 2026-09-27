"""A session close preview warning for an automatic backlog move."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class AutoBacklogWarningEntry(BaseModel):
    """
    An item the close will move out of an earlier session's backlog into the
    project backlog, without a disposition asking for it. The caller names
    each one to the user before confirming.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["auto_backlog"] = "auto_backlog"
    key: str
    origin_session: str | None
    target: Literal["project_backlog"] = "project_backlog"
