"""Clients through which sessions are started and writes are made."""

from enum import StrEnum


class Client(StrEnum):
    """Where a write came from; recorded on sessions and on every event."""

    CHAT = "chat"
    CODE = "code"
    PASTE = "paste"
    CLI = "cli"
