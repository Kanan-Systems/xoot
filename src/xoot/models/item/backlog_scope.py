"""Which backlog a backlog read covers."""

from typing import Literal

BacklogScope = Literal["session", "project", "unfiled"]
"""
session: parked in a session's backlog; project: in the project backlog;
unfiled: open subtasks with no batch.
"""
