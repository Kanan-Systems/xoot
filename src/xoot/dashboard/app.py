"""
The dashboard application: the API routes, the static bundle and the
single-page fallback, wrapped in the guard.
"""

from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp

from xoot.dashboard.api import api_routes
from xoot.dashboard.api_error import ApiError
from xoot.dashboard.errors import UNAVAILABLE, error_response
from xoot.dashboard.guard import guard
from xoot.dashboard.launch_codes import LaunchCodes

STATIC = Path(__file__).parent / "static"


def create_app(
    db_path: Path,
    token: str,
    port: int,
    static_dir: Path = STATIC,
    launch_codes: LaunchCodes | None = None,
) -> ASGIApp:
    """
    Build the guarded dashboard application.

    Args:
        - db_path (Path): the database each API request opens.
        - token (str): the per-launch token the guard requires.
        - port (int): the served port, part of the Host allowlist.
        - static_dir (Path): the built bundle: index.html and assets/.
        - launch_codes (LaunchCodes | None): one-time codes for --open.

    Returns:
        - app (ASGIApp): the application, guard outermost.
    """
    index = static_dir / "index.html"

    async def spa(_request: Request) -> Response:
        # Client-side routes all load the same page; it holds no data.
        if not index.is_file():
            return error_response(
                ApiError(
                    UNAVAILABLE, "BundleMissing", "the dashboard bundle is missing"
                )
            )
        return FileResponse(index, media_type="text/html")

    app = Starlette(
        routes=[
            *api_routes(db_path),
            Mount(
                "/assets",
                app=StaticFiles(directory=static_dir / "assets", check_dir=False),
            ),
            Route("/{path:path}", spa, methods=["GET"]),
        ]
    )
    return guard(app, token=token, port=port, launch_codes=launch_codes)
