"""Raised when an optimistic update was based on a stale version."""

from xoot.exceptions.xoot_error import XootError
from xoot.models.event.actor import Actor


class VersionConflictError(XootError):
    """
    The entity changed since the version the caller read.

    Carries what changed and who changed it, taken from the event log, so the
    caller can re-read and decide instead of blindly retrying.
    """

    def __init__(
        self,
        key: str,
        current_version: int,
        changed_fields: tuple[str, ...],
        actors: tuple[Actor, ...],
    ) -> None:
        """
        Record the conflict details.

        Args:
            - key (str): key of the item or decision, e.g. "xoot-12".
            - current_version (int): version now stored.
            - changed_fields (tuple[str, ...]): fields changed since the
              expected version, sorted.
            - actors (tuple[Actor, ...]): who made those changes, in order.
        """
        super().__init__(
            f"{key} is at version {current_version}; "
            f"changed since: {', '.join(changed_fields) or 'nothing recorded'}"
        )
        self.key = key
        self.current_version = current_version
        self.changed_fields = changed_fields
        self.actors = actors
