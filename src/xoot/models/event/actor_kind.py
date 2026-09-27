"""Who performed a write."""

from enum import StrEnum


class ActorKind(StrEnum):
    """
    Claude acting through a client, the user directly, or xoot itself.

    SYSTEM is for changes xoot derives from another actor's write (stale
    backlog moves, workflow remaps); they keep that write's client and
    session.
    """

    CLAUDE = "claude"
    USER = "user"
    SYSTEM = "system"
