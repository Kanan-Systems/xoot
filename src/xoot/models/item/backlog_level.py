"""Where a backlog item sits."""

from typing import Literal

BacklogLevel = Literal["project", "goal", "batch"]
"""project: the project backlog; goal: a goal's own; batch: a batch's."""
