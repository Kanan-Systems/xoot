"""
The request guard: every request passes through it before any route.

In order it checks the Host header against the allowlist (400), the method
(405: the dashboard is read-only), exchanges a ?token query for the session
cookie (a redirect that drops the query), and on /api requires a same-origin
Origin, if any (403), and the cookie (401). It adds the security headers to
every response, its own refusals included. Token comparisons are constant
time, and the token is never logged or echoed.
"""

import hmac
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qs, quote

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import cookie_parser
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from xoot.dashboard.headers import ALWAYS, API_ONLY
from xoot.dashboard.schemas.error_output import ErrorOutput

COOKIE = "xoot_token"
ALLOWED_METHODS = ("GET", "HEAD")
HOST_NAMES = ("xoot.localhost", "localhost", "127.0.0.1")


def guard(app: ASGIApp, token: str, port: int) -> ASGIApp:
    """
    Wrap an app in the dashboard's access rules for one launch.

    Args:
        - app (ASGIApp): the routed application.
        - token (str): the per-launch token.
        - port (int): the port the server listens on.

    Returns:
        - guarded (ASGIApp): the app behind the guard.
    """
    expected = token.encode("ascii")
    hosts = frozenset(f"{name}:{port}" for name in HOST_NAMES)

    def valid(candidate: str) -> bool:
        try:
            given = candidate.encode("ascii")
        except UnicodeEncodeError:
            return False
        return hmac.compare_digest(given, expected)

    def refusal(scope: Scope, is_api: bool) -> Response | None:
        headers = Headers(scope=scope)
        host = headers.get("host")
        early = _host_or_method(scope, host, hosts)
        if early is not None:
            return early
        offered = parse_qs(scope["query_string"].decode("latin-1")).get("token")
        if offered is not None:
            if len(offered) == 1 and valid(offered[0]):
                return _exchange(scope["path"], offered[0])
            return _error(401, "Unauthorized", "the token is not valid")
        return api_access(headers, host) if is_api else None

    def api_access(headers: Headers, host: str | None) -> Response | None:
        origin = headers.get("origin")
        if origin is not None and origin != f"http://{host}":
            return _error(403, "Forbidden", "the Origin is not allowed")
        cookie = cookie_parser(headers.get("cookie", "")).get(COOKIE)
        if cookie is None or not valid(cookie):
            return _error(401, "Unauthorized", "a valid session cookie is required")
        return None

    async def guarded(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await app(scope, receive, send)
            return
        if scope["type"] != "http":
            # Uvicorn runs with websockets off; anything else is dropped.
            return
        path: str = scope["path"]
        is_api = path == "/api" or path.startswith("/api/")
        send = _with_headers(send, is_api)
        refused = refusal(scope, is_api)
        if refused is not None:
            await refused(scope, receive, send)
            return
        await app(scope, receive, send)

    return guarded


def _host_or_method(
    scope: Scope, host: str | None, hosts: frozenset[str]
) -> Response | None:
    """Refuse a Host outside the allowlist (400) or a write method (405)."""
    if host not in hosts:
        return _error(400, "BadRequest", "the Host header is not allowed")
    if scope["method"] not in ALLOWED_METHODS:
        response = _error(405, "MethodNotAllowed", "the dashboard is read-only")
        response.headers["allow"] = ", ".join(ALLOWED_METHODS)
        return response
    return None


def _exchange(path: str, token: str) -> Response:
    """Set the cookie and redirect to the same path without the query."""
    response = Response(status_code=303, headers={"location": _same_path(path)})
    response.headers["cache-control"] = "no-store"
    response.set_cookie(COOKIE, token, path="/", httponly=True, samesite="strict")
    return response


def _same_path(path: str) -> str:
    # "//host" or a backslash would make the redirect leave this origin.
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        return "/"
    return quote(path, safe="/")


def _error(status: int, error: str, message: str) -> JSONResponse:
    body = ErrorOutput(error=error, message=message)
    return JSONResponse(body.model_dump(), status_code=status)


def _with_headers(send: Send, is_api: bool) -> Callable[[Message], Awaitable[None]]:
    extra = {**ALWAYS, **(API_ONLY if is_api else {})}

    async def wrapped(message: Message) -> None:
        if message["type"] == "http.response.start":
            headers = MutableHeaders(scope=message)
            for name, value in extra.items():
                headers[name] = value
        await send(message)

    return wrapped
