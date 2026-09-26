"""Session lifecycle status."""

from enum import StrEnum


class SessionStatus(StrEnum):
    """Sessions start open and are closed exactly once."""

    OPEN = "open"
    CLOSED = "closed"
