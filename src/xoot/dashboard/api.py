"""
The /api/v1 routes. Each handler validates its query, runs one read on a
worker thread and returns the response model as JSON; any failure becomes
the safe error body.
"""

import sqlite3
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from xoot import __version__
from xoot.dashboard.api_error import ApiError
from xoot.dashboard.errors import NOT_FOUND, error_response, from_exception
from xoot.dashboard.params.no_params import NoParams
from xoot.dashboard.params.tree_params import TreeParams
from xoot.dashboard.reads import run_read
from xoot.dashboard.schemas.meta_output import MetaOutput
from xoot.dashboard.views.project_views import (
    backlog_view,
    brief_view,
    changes_view,
    decisions_view,
    projects_view,
    tree_view,
    workflow_view,
)
from xoot.dashboard.views.record_views import decision_view, item_view

PREFIX = "/api/v1"

type Build = Callable[[Request], Callable[[sqlite3.Connection], BaseModel]]


def api_routes(db_path: Path) -> list[Route]:
    """
    Build the API routes over one database file.

    Args:
        - db_path (Path): the database every request opens.

    Returns:
        - routes (list[Route]): GET routes (HEAD implied), then a JSON 404
          for any other /api path.
    """

    def read(build: Build) -> Callable[[Request], object]:
        async def endpoint(request: Request) -> Response:
            try:
                model = await run_read(db_path, build(request))
            except ApiError as error:
                return error_response(error)
            return JSONResponse(model.model_dump(mode="json"))

        return endpoint

    def path(request: Request, name: str) -> str:
        return str(request.path_params[name])

    routes = [
        ("/projects", lambda r: _no_query(r, projects_view)),
        (
            "/projects/{prefix}/brief",
            lambda r: _no_query(r, lambda c: brief_view(c, path(r, "prefix"))),
        ),
        ("/projects/{prefix}/tree", lambda r: _tree(r, path(r, "prefix"))),
        (
            # {key:path} keeps the slashes of a nested key such as goal-1/batch-2.
            "/projects/{prefix}/items/{key:path}",
            lambda r: _no_query(
                r, lambda c: item_view(c, path(r, "prefix"), path(r, "key"))
            ),
        ),
        (
            "/projects/{prefix}/backlog",
            lambda r: _no_query(r, lambda c: backlog_view(c, path(r, "prefix"))),
        ),
        (
            "/projects/{prefix}/decisions",
            lambda r: _no_query(r, lambda c: decisions_view(c, path(r, "prefix"))),
        ),
        (
            "/projects/{prefix}/decisions/{key:path}",
            lambda r: _no_query(
                r, lambda c: decision_view(c, path(r, "prefix"), path(r, "key"))
            ),
        ),
        (
            "/projects/{prefix}/changes",
            lambda r: _no_query(r, lambda c: changes_view(c, path(r, "prefix"))),
        ),
        (
            "/projects/{prefix}/workflow",
            lambda r: _no_query(r, lambda c: workflow_view(c, path(r, "prefix"))),
        ),
    ]
    return [
        Route(f"{PREFIX}/meta", _meta, methods=["GET"]),
        *(Route(f"{PREFIX}{p}", read(b), methods=["GET"]) for p, b in routes),
        Route("/api", _api_not_found, methods=["GET"]),
        Route("/api/{rest:path}", _api_not_found, methods=["GET"]),
    ]


async def _meta(request: Request) -> Response:
    try:
        _query(request, NoParams)
    except ApiError as error:
        return error_response(error)
    return JSONResponse(MetaOutput(version=__version__).model_dump())


async def _api_not_found(_request: Request) -> Response:
    return error_response(ApiError(NOT_FOUND, "NotFoundError", "no such endpoint"))


def _no_query[M: BaseModel](
    request: Request, view: Callable[[sqlite3.Connection], M]
) -> Callable[[sqlite3.Connection], M]:
    _query(request, NoParams)
    return view


def _tree(request: Request, prefix: str) -> Callable[[sqlite3.Connection], BaseModel]:
    params = _query(request, TreeParams)
    return lambda conn: tree_view(conn, prefix, params)


def _query[P: BaseModel](request: Request, model: type[P]) -> P:
    """Validate the query string; a bad or unknown parameter is a 400."""
    try:
        return model.model_validate(dict(request.query_params))
    except ValidationError as exc:
        raise from_exception(exc) from exc
