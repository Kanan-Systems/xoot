"""
Turning domain and validation errors into safe API errors.

The message is the MCP server's safe_message, split into its class name and
reason, so the dashboard leaks exactly as little as the tools do.
"""

from pydantic import ValidationError
from starlette.responses import JSONResponse

from xoot.dashboard.api_error import ApiError
from xoot.dashboard.schemas.error_output import ErrorOutput
from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.exceptions.not_found_error import NotFoundError
from xoot.exceptions.store_error import StoreError
from xoot.exceptions.stored_data_error import StoredDataError
from xoot.exceptions.xoot_error import XootError
from xoot.server.errors import safe_message
from xoot.utils.keys import PREFIX_KEY, is_key

NOT_FOUND = 404
BAD_REQUEST = 400
INTERNAL = 500
UNAVAILABLE = 503


def from_exception(exc: XootError | ValidationError) -> ApiError:
    """
    Map an error raised by a read to its status and safe body.

    Args:
        - exc (XootError | ValidationError): the error.

    Returns:
        - error (ApiError): 404 for a missing or foreign record, 500 for
          stored data this code cannot read, 503 for a database that cannot
          serve, 400 otherwise.
    """
    name, _, reason = safe_message(exc).partition(": ")
    if isinstance(exc, (NotFoundError, CrossProjectError)):
        status = NOT_FOUND
    elif isinstance(exc, StoredDataError):
        status = INTERNAL
    elif isinstance(exc, StoreError):
        status = UNAVAILABLE
    else:
        status = BAD_REQUEST
    return ApiError(status, name, reason)


def not_found(key: str) -> ApiError:
    """
    Build the 404 for a key or prefix that names nothing.

    A well-formed key or prefix is echoed (it holds only [a-z0-9/:-]); any
    other text is arbitrary input and is not.

    Args:
        - key (str): the key or prefix as the caller sent it.

    Returns:
        - error (ApiError): a NotFoundError body.
    """
    well_formed = is_key(key) or PREFIX_KEY.fullmatch(key) is not None
    ref = key if well_formed else "malformed key"
    return ApiError(NOT_FOUND, "NotFoundError", f"not found: {ref}")


def error_response(error: ApiError) -> JSONResponse:
    """
    Render an ApiError as its JSON response.

    Args:
        - error (ApiError): the error.

    Returns:
        - response (JSONResponse): {"error": ..., "message": ...}.
    """
    body = ErrorOutput(error=error.error, message=error.message)
    return JSONResponse(body.model_dump(), status_code=error.status)
