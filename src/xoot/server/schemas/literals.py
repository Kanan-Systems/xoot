"""Closed value sets shared by several tool schemas."""

from typing import Literal

ResolvedBy = Literal["alias", "roots", "cwd"]
"""How a project-level tool found its project."""

Phase = Literal["preview", "applied"]
"""Whether a two-phase call only planned the change or wrote it."""

UpdateMode = Literal["update", "drop", "reparent"]
"""Which path an item_update took."""

BacklogScope = Literal["session", "project", "unfiled"]
"""Which backlog backlog_list reads."""
