"""Raised when other connections keep a maintenance step from running."""

from xoot.exceptions.store_error import StoreError

BUSY_MESSAGE = "database busy: close clients and retry"


class DatabaseBusyError(StoreError):
    """
    Another connection held a lock past the busy timeout, so a checkpoint
    or VACUUM could not finish. Nothing was lost; closing the other clients
    (such as a running xoot-mcp) and retrying is enough.

    The message is fixed; the driver's error, if any, is chained as
    __cause__.
    """

    def __init__(self) -> None:
        """Use the fixed message."""
        super().__init__(BUSY_MESSAGE)
