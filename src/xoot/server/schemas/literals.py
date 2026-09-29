"""Closed value sets shared by several tool schemas."""

from typing import Annotated, Literal

from pydantic import Field

from xoot.models.item.backlog_scope import BacklogScope

ResolvedBy = Annotated[
    Literal["prefix", "alias", "roots", "cwd"],
    Field(
        description=(
            "How the project was found: prefix (the name given is its key "
            "prefix), alias (the name given is one of its aliases), roots (a "
            "client root) or cwd (the working directory)."
        )
    ),
]
"""How a project-level call found its project; described in every schema."""

Phase = Literal["preview", "applied"]
"""Whether a two-phase call only planned the change or wrote it."""

UpdateMode = Literal["update", "drop", "reparent"]
"""Which path an item_update took."""

__all__ = ["BacklogScope", "Phase", "ResolvedBy", "UpdateMode"]
