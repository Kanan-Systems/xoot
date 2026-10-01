"""
The CLI's error lines and the exit code each error maps to.

A line is "error: <Class>: <reason>". Errors whose messages are built only
from fixed text and validated values (keys, slugs, state names, paths) keep
their message; every other error gets the server's fixed reason, so driver
text and SQL never reach the terminal. A failed paste op is its op number
followed by its own error, rendered by the same rules. Everything printed is
cleaned.
"""

from pydantic import ValidationError

from xoot.cli import exit_codes
from xoot.cli.render.text import clean
from xoot.exceptions.confirmation_error import ConfirmationError
from xoot.exceptions.database_access_error import DatabaseAccessError
from xoot.exceptions.database_busy_error import DatabaseBusyError
from xoot.exceptions.duplicate_error import DuplicateError
from xoot.exceptions.not_found_error import NotFoundError
from xoot.exceptions.paste_error import PasteError
from xoot.exceptions.paste_op_error import PasteOpError
from xoot.exceptions.project_resolution_error import ProjectResolutionError
from xoot.exceptions.redaction_error import RedactionError
from xoot.exceptions.schema_version_error import SchemaVersionError
from xoot.exceptions.store_open_error import StoreOpenError
from xoot.exceptions.stored_data_error import StoredDataError
from xoot.exceptions.unsafe_path_error import UnsafePathError
from xoot.exceptions.update_path_error import UpdatePathError
from xoot.exceptions.workflow_file_error import WorkflowFileError
from xoot.exceptions.workflow_mapping_error import WorkflowMappingError
from xoot.exceptions.xoot_error import XootError
from xoot.server.errors import safe_message

LOC_MAX = 64

_DETAILED: tuple[type[XootError], ...] = (
    ConfirmationError, DatabaseBusyError, DuplicateError, NotFoundError,
    PasteError, ProjectResolutionError, RedactionError, SchemaVersionError,
    StoreOpenError, StoredDataError, UnsafePathError, UpdatePathError,
    WorkflowFileError, WorkflowMappingError,
)  # fmt: skip
_BUSY_CODES = ("SQLITE_BUSY", "SQLITE_LOCKED")


def error_message(exc: XootError | ValidationError) -> str:
    """
    Build the stderr line for a refused command.

    Args:
        - exc (XootError | ValidationError): the error.

    Returns:
        - line (str): "error: <Class>: <reason>".
    """
    if isinstance(exc, ValidationError):
        return f"error: ValidationError: {_validation(exc)}"
    if isinstance(exc, PasteOpError) and isinstance(
        exc.cause, (XootError, ValidationError)
    ):
        # The op's own error, rendered by these same rules, after its number.
        inner = error_message(exc.cause).removeprefix("error: ")
        return f"error: PasteOpError: {exc.prefix}: {inner}"
    if isinstance(exc, _DETAILED):
        return f"error: {type(exc).__name__}: {clean(str(exc))}"
    return f"error: {safe_message(exc)}"


def exit_code(exc: XootError | ValidationError) -> int:
    """
    Map a refused command's error to the process exit code.

    Args:
        - exc (XootError | ValidationError): the error.

    Returns:
        - code (int): UNAVAILABLE for an unsafe path, a busy database or
          stored data this code cannot read, ERROR otherwise.
    """
    if isinstance(exc, PasteOpError) and isinstance(
        exc.cause, (XootError, ValidationError)
    ):
        return exit_code(exc.cause)
    if isinstance(exc, (UnsafePathError, DatabaseBusyError, StoredDataError)):
        return exit_codes.UNAVAILABLE
    if isinstance(exc, DatabaseAccessError):
        name = exc.sqlite_errorname or ""
        if name.startswith(_BUSY_CODES):
            return exit_codes.UNAVAILABLE
    return exit_codes.ERROR


def _validation(exc: ValidationError) -> str:
    """Each failing location and pydantic's message, never the input value."""
    parts = []
    for error in exc.errors():
        location = ".".join(clean(str(part))[:LOC_MAX] for part in error["loc"])
        parts.append(f"{location or 'input'}: {clean(error['msg'])}")
    return "; ".join(sorted(set(parts)))
