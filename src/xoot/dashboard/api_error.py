"""The exception a dashboard handler raises to answer with an error."""

from typing import Any


class ApiError(Exception):
    """
    An HTTP status plus the safe error body. The message and details are
    always built from fixed text, stored keys or validated values, so they
    can be sent as is.
    """

    def __init__(
        self,
        status: int,
        error: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Hold the response parts.

        Args:
            - status (int): the HTTP status code.
            - error (str): the error class name.
            - message (str): the safe message.
            - details (dict[str, Any] | None): structured facts a client can
              act on, such as a conflict's current version; None when there
              are none.
        """
        super().__init__(message)
        self.status = status
        self.error = error
        self.message = message
        self.details = details
