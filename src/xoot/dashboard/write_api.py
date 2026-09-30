"""
The /api/v1 write routes. Each handler refuses any query string, validates
the JSON body against its request model, runs the write on a worker thread
as the dashboard user and returns the output model as JSON; any failure
becomes the safe {error, message, details} body.

The guard lets POST and PATCH through only to these routes, and only from
the served origin with the session cookie and a JSON body, so a body is
never read before those checks pass. It is then capped at MAX_BODY_BYTES
(413) on the bytes actually received, whatever Content-Length says or when
it is chunked: at most the cap plus one received chunk is ever buffered.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from xoot.dashboard.api_error import ApiError
from xoot.dashboard.params.no_params import NoParams
from xoot.dashboard.requests.capture_request import CaptureRequest
from xoot.dashboard.requests.cover_request import CoverRequest
from xoot.dashboard.requests.decision_create_request import DecisionCreateRequest
from xoot.dashboard.requests.decision_update_request import DecisionUpdateRequest
from xoot.dashboard.requests.item_create_request import ItemCreateRequest
from xoot.dashboard.requests.item_update_request import ItemUpdateRequest
from xoot.dashboard.requests.move_request import MoveRequest
from xoot.dashboard.requests.project_rename_request import ProjectRenameRequest
from xoot.dashboard.requests.push_request import PushRequest
from xoot.dashboard.views import write_views
from xoot.dashboard.write_errors import write_error, write_error_response
from xoot.dashboard.writes import DASHBOARD, run_write

PREFIX = "/api/v1"
CREATED = 201
OK = 200
TOO_LARGE = 413
# Twice the largest valid body (a 32 KiB body field plus the rest).
MAX_BODY_BYTES = 64 * 1024

type Build = Callable[[dict[str, str], Any], write_views.Work[BaseModel]]


@dataclass(frozen=True)
class WriteSpec:
    """One write route: method, path under /api/v1, body model, work, status."""

    method: str
    path: str
    body: type[BaseModel]
    build: Build
    status: int = OK


WRITES: tuple[WriteSpec, ...] = (
    WriteSpec(
        "POST",
        "/projects/{prefix}/items",
        ItemCreateRequest,
        lambda p, b: write_views.create_item_work(p["prefix"], b, DASHBOARD),
        CREATED,
    ),
    WriteSpec(
        "PATCH",
        # {key:path} keeps the slashes of a nested key such as goal-1/batch-2.
        "/projects/{prefix}/items/{key:path}",
        ItemUpdateRequest,
        lambda p, b: write_views.update_item_work(p["prefix"], p["key"], b, DASHBOARD),
    ),
    WriteSpec(
        "POST",
        "/projects/{prefix}/moves",
        MoveRequest,
        lambda p, b: write_views.move_work(p["prefix"], b, DASHBOARD),
    ),
    WriteSpec(
        "POST",
        "/projects/{prefix}/backlog",
        CaptureRequest,
        lambda p, b: write_views.capture_work(p["prefix"], b, DASHBOARD),
        CREATED,
    ),
    WriteSpec(
        "POST",
        "/projects/{prefix}/backlog/covers",
        CoverRequest,
        lambda p, b: write_views.cover_work(p["prefix"], b, DASHBOARD),
    ),
    WriteSpec(
        "POST",
        "/projects/{prefix}/backlog/pushes",
        PushRequest,
        lambda p, b: write_views.push_work(p["prefix"], b, DASHBOARD),
    ),
    WriteSpec(
        "POST",
        "/projects/{prefix}/decisions",
        DecisionCreateRequest,
        lambda p, b: write_views.create_decision_work(p["prefix"], b, DASHBOARD),
        CREATED,
    ),
    WriteSpec(
        "PATCH",
        "/projects/{prefix}/decisions/{key:path}",
        DecisionUpdateRequest,
        lambda p, b: write_views.update_decision_work(
            p["prefix"], p["key"], b, DASHBOARD
        ),
    ),
    WriteSpec(
        "PATCH",
        "/projects/{prefix}",
        ProjectRenameRequest,
        lambda p, b: write_views.rename_project_work(p["prefix"], b, DASHBOARD),
    ),
)


def write_routes(db_path: Path) -> list[Route]:
    """
    Build the write routes over one database file.

    Args:
        - db_path (Path): the database every request opens.

    Returns:
        - routes (list[Route]): one POST or PATCH route per entry of WRITES.
    """

    def route(spec: WriteSpec) -> Route:
        async def endpoint(request: Request) -> Response:
            try:
                body = await _body(request, spec.body)
                params = {k: str(v) for k, v in request.path_params.items()}
                result = await run_write(db_path, spec.build(params, body))
            except ApiError as error:
                return write_error_response(error)
            return JSONResponse(result.model_dump(mode="json"), status_code=spec.status)

        return Route(f"{PREFIX}{spec.path}", endpoint, methods=[spec.method])

    return [route(spec) for spec in WRITES]


async def _body(request: Request, model: type[BaseModel]) -> BaseModel:
    """Refuse a query string, read the capped body, then validate it (422)."""
    try:
        NoParams.model_validate(dict(request.query_params))
        return model.model_validate_json(await _capped(request))
    except ValidationError as exc:
        raise write_error(exc) from exc


async def _capped(request: Request) -> bytes:
    """Read the body, refusing it (413) as soon as it passes MAX_BODY_BYTES."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise _too_large()
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BODY_BYTES:
            raise _too_large()
        chunks.append(chunk)
    return b"".join(chunks)


def _too_large() -> ApiError:
    return ApiError(
        TOO_LARGE,
        "PayloadTooLarge",
        f"a write body may be at most {MAX_BODY_BYTES} bytes",
        {"max_bytes": MAX_BODY_BYTES},
    )
