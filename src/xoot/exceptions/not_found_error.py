"""Raised when a referenced entity does not exist."""

from xoot.exceptions.xoot_error import XootError


class NotFoundError(XootError):
    """A lookup by id, key, alias or path found nothing."""

    def __init__(self, entity: str, ref: object) -> None:
        """
        Record what was looked up.

        Args:
            - entity (str): entity kind, e.g. "item".
            - ref (object): the id, key or name that was not found.
        """
        super().__init__(f"{entity} {ref!r} not found")
        self.entity = entity
        self.ref = ref
