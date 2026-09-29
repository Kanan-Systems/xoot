"""Closed value sets shared by several tool schemas."""

from typing import Annotated, Literal

from pydantic import Field

ResolvedBy = Annotated[
    Literal["prefix", "alias", "qualified", "roots", "cwd"],
    Field(
        description=(
            "How the project was found: prefix or alias (the project argument "
            "is its key prefix or one of its aliases), qualified (a key was "
            "given as <prefix>:<key>), roots (a client root) or cwd (the "
            "working directory)."
        )
    ),
]
"""How a call found its project; described in every schema."""

Phase = Literal["preview", "applied"]
"""Whether a two-phase call only planned the change or wrote it."""

UpdateMode = Literal["update", "drop", "reparent"]
"""Which path an item_update took."""

WorkKind = Literal["goal", "batch", "subtask"]
"""The kinds item_create and items_create_bulk make; backlog comes from capture."""
