"""The planned effect of closing a session."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from xoot.models.session.disposition import Disposition
from xoot.server.schemas.auto_backlog_warning_entry import AutoBacklogWarningEntry
from xoot.server.schemas.change_entry import ChangeEntry
from xoot.server.schemas.close_warning_entry import CloseWarningEntry

CloseWarningItem = Annotated[
    CloseWarningEntry | AutoBacklogWarningEntry, Field(discriminator="kind")
]


class ClosePreview(BaseModel):
    """
    required lists the linked items that need a disposition; a preview is
    only returned once every one has one. warnings holds parent_state entries
    and one auto_backlog entry per item in auto_backlog.
    """

    model_config = ConfigDict(frozen=True)

    required: list[str]
    dispositions: dict[str, Disposition]
    changes: list[ChangeEntry]
    auto_backlog: list[ChangeEntry]
    warnings: list[CloseWarningItem]
