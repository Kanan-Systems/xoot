"""Who performed a write."""

from enum import StrEnum


class ActorKind(StrEnum):
    """Claude acting through a client, or the user directly."""

    CLAUDE = "claude"
    USER = "user"
