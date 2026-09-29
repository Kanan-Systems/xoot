"""Who performed a write."""

from enum import StrEnum


class ActorKind(StrEnum):
    """
    Claude acting through a client, the user directly, or xoot itself.

    SYSTEM is for changes xoot derives from another actor's write (a goal or
    batch completing or reopening, workflow remaps); they keep that write's
    client.
    """

    CLAUDE = "claude"
    USER = "user"
    SYSTEM = "system"
