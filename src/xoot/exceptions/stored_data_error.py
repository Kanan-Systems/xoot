"""Raised when a stored row cannot be read into its model."""

from xoot.exceptions.xoot_error import XootError

RESTART_HINT = (
    "an older xoot process may still be running; restart the clients that use "
    "xoot (quit Claude Desktop completely, restart Claude Code) so all of them "
    "run this version"
)


class StoredDataError(XootError):
    """
    A row read from the database does not fit the model this code has.

    This is not a caller's mistake: the input came from the database. The
    usual cause is a process started before an upgrade reading rows a newer
    xoot wrote, so the message says so instead of "invalid arguments".
    """

    def __init__(self, table: str, row_id: int | None, field: str, value: str) -> None:
        """
        Build the message from the table, row, field and shown value.

        Args:
            - table (str): the table the row came from (a fixed name).
            - row_id (int | None): the row's id, None when it has none.
            - field (str): the column (or nested path) that failed.
            - value (str): the value as it may be shown; the caller decides
              how much of a stored value is safe to echo.
        """
        row = "unknown" if row_id is None else str(row_id)
        super().__init__(
            f"stored data could not be read: {table} row {row}, field {field}: "
            f"unexpected value {value}; {RESTART_HINT}"
        )
        self.table = table
        self.row_id = row_id
        self.field = field
        self.value = value
