"""Clients through which writes are made."""

from enum import StrEnum


class Client(StrEnum):
    """Where a write came from; recorded on every event."""

    CHAT = "chat"
    CODE = "code"
    PASTE = "paste"
    CLI = "cli"
