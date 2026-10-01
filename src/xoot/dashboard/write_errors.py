"""
Turning errors raised by a dashboard write into safe API errors.

Every body has the stable shape {error, message, details}. The message is
the MCP server's safe_message reason, except for a taken alias, which
names the validated alias it was asked for but never the project that holds
it. details carry only stored keys, versions, counts, actor labels and that
alias.

  404  a record the write names does not exist, or is another project's
  409  a version conflict, a taken name, a token that cannot be used (spent,
       expired, another client, plan changed), or a record changed mid-write
  422  invalid input, or a domain rule refused the write (hierarchy,
       workflow, open children, plan size, backlog rules)
  500  stored data could not be read (an older xoot process, usually)
  503  the database could not serve
"""

from typing import Any

from pydantic import ValidationError
from starlette.responses import JSONResponse

from xoot.dashboard.api_error import ApiError
from xoot.dashboard.requests.project_rename_request import ProjectRenameRequest
from xoot.dashboard.schemas.write_error_output import WriteErrorOutput
from xoot.exceptions.confirm_token_error import ConfirmTokenError
from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.exceptions.duplicate_error import DuplicateError
from xoot.exceptions.integrity_violation_error import IntegrityViolationError
from xoot.exceptions.not_found_error import NotFoundError
from xoot.exceptions.open_children_error import OpenChildrenError
from xoot.exceptions.plan_size_error import PlanSizeError
from xoot.exceptions.stale_write_error import StaleWriteError
from xoot.exceptions.store_error import StoreError
from xoot.exceptions.stored_data_error import StoredDataError
from xoot.exceptions.update_path_error import UpdatePathError
from xoot.exceptions.version_conflict_error import VersionConflictError
from xoot.exceptions.xoot_error import XootError
from xoot.server.errors import KNOWN_FIELDS, PUBLIC_NAMES, safe_message

NOT_FOUND = 404
CONFLICT = 409
UNPROCESSABLE = 422
INTERNAL = 500
UNAVAILABLE = 503
# The tools' field names plus the rename body's (name, alias): schema names,
# never caller text, so a refusal can say which field it was.
_FIELDS = KNOWN_FIELDS | frozenset(ProjectRenameRequest.model_fields)

_CONFLICTS: tuple[type[XootError], ...] = (
    ConfirmTokenError, DuplicateError, IntegrityViolationError, StaleWriteError,
    VersionConflictError,
)  # fmt: skip


def write_error(exc: XootError | ValidationError) -> ApiError:
    """
    Map an error raised by a write to its status and safe body.

    Args:
        - exc (XootError | ValidationError): the error.

    Returns:
        - error (ApiError): the status, class name, reason and details.
    """
    if isinstance(exc, DuplicateError) and exc.field == "alias":
        return _taken_alias(exc)
    if isinstance(exc, UpdatePathError):
        # Fixed text only, as the MCP tool already shows it.
        return ApiError(UNPROCESSABLE, "UpdatePathError", str(exc), {})
    name, _, reason = safe_message(exc, _FIELDS).partition(": ")
    return ApiError(_status(exc), name, reason, _details(exc))


def _taken_alias(exc: DuplicateError) -> ApiError:
    """Name the alias, not the project or prefix that already holds it."""
    where = "this project" if exc.own else "another project"
    message = f"alias {exc.value!r} is already used by {where}"
    return ApiError(CONFLICT, "DuplicateError", message, {"alias": exc.value})


def write_error_response(error: ApiError) -> JSONResponse:
    """
    Render an ApiError as a write route's response.

    Args:
        - error (ApiError): the error.

    Returns:
        - response (JSONResponse): {"error", "message", "details"}; details
          is {} when the error carries none.
    """
    body = WriteErrorOutput(
        error=error.error, message=error.message, details=error.details or {}
    )
    return JSONResponse(body.model_dump(mode="json"), status_code=error.status)


def _status(exc: XootError | ValidationError) -> int:
    if isinstance(exc, (NotFoundError, CrossProjectError)):
        return NOT_FOUND
    if isinstance(exc, _CONFLICTS):
        return CONFLICT
    if isinstance(exc, StoredDataError):
        return INTERNAL
    if isinstance(exc, StoreError):
        return UNAVAILABLE
    return UNPROCESSABLE


def _details(exc: XootError | ValidationError) -> dict[str, Any] | None:
    if isinstance(exc, VersionConflictError):
        return {
            "key": exc.key,
            "current_version": exc.current_version,
            "changed_fields": [PUBLIC_NAMES.get(f, f) for f in exc.changed_fields],
            "actors": [
                {"kind": str(actor.kind), "client": str(actor.client)}
                for actor in exc.actors
            ],
        }
    if isinstance(exc, OpenChildrenError):
        return {"key": exc.key, "open_keys": list(exc.open_keys)}
    if isinstance(exc, PlanSizeError):
        return {"key": exc.key, "size": exc.size, "cap": exc.cap}
    return None
