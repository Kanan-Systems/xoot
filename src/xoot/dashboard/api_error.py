"""The exception a dashboard handler raises to answer with an error."""


class ApiError(Exception):
    """
    An HTTP status plus the safe error body. The message is always built
    from fixed text or validated values, so it can be sent as is.
    """

    def __init__(self, status: int, error: str, message: str) -> None:
        """
        Hold the response parts.

        Args:
            - status (int): the HTTP status code.
            - error (str): the error class name.
            - message (str): the safe message.
        """
        super().__init__(message)
        self.status = status
        self.error = error
        self.message = message
