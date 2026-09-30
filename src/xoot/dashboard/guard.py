"""
The request guard: every request passes through it before any route.

In order it checks the Host header against the allowlist (400), the method
(405), exchanges a ?token query, or a one-time ?launch code, for the session
cookie (a redirect that drops the query), and on /api requires a same-origin
Origin, if any (403), and the cookie (401).

GET and HEAD are reads. POST and PATCH are writes, allowed only on the
registered write routes (any other method or path is a 405). A write is
never authenticated by a query: it needs the cookie, an Origin header that
is present and names the served origin (403), and a JSON body (415). An
absent Origin is refused on a write because only the dashboard's own page
may write; a page on another origin, localhost ports included, sends its
own Origin and a same-site cookie.
The cookie is named after the port, so dashboards on two ports never
overwrite each other's cookie. It adds the security headers to every
response, its own refusals included. Token comparisons are constant time,
and neither the token nor a code is ever logged or echoed.
"""

import hmac
from collections.abc import Awaitable, Callable, Sequence
from urllib.parse import parse_qs, quote

from pydantic import BaseModel
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import cookie_parser
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from xoot.dashboard.headers import ALWAYS, API_ONLY
from xoot.dashboard.launch_codes import LaunchCodes
from xoot.dashboard.schemas.error_output import ErrorOutput
from xoot.dashboard.schemas.write_error_output import WriteErrorOutput

COOKIE_PREFIX = "xoot_token_"
ALLOWED_METHODS = ("GET", "HEAD")
WRITE_METHODS = ("POST", "PATCH")
JSON = "application/json"
HOST_NAMES = ("xoot.localhost", "localhost", "127.0.0.1")


def cookie_name(port: int) -> str:
    """
    Name the session cookie of the dashboard on one port.

    Args:
        - port (int): the served port.

    Returns:
        - name (str): "xoot_token_<port>".
    """
    return f"{COOKIE_PREFIX}{port}"


def guard(
    app: ASGIApp,
    token: str,
    port: int,
    launch_codes: LaunchCodes | None = None,
    writes: Sequence[BaseRoute] = (),
) -> ASGIApp:
    """
    Wrap an app in the dashboard's access rules for one launch.

    Args:
        - app (ASGIApp): the routed application.
        - token (str): the per-launch token.
        - port (int): the port the server listens on.
        - launch_codes (LaunchCodes | None): the one-time codes a ?launch
          query may redeem; none are accepted when None.
        - writes (Sequence[BaseRoute]): the write routes; a POST or PATCH
          must match one of them in full, method included.

    Returns:
        - guarded (ASGIApp): the app behind the guard.
    """
    expected = token.encode("ascii")
    hosts = frozenset(f"{name}:{port}" for name in HOST_NAMES)
    cookie = cookie_name(port)

    def valid(candidate: str) -> bool:
        try:
            given = candidate.encode("ascii")
        except UnicodeEncodeError:
            return False
        return hmac.compare_digest(given, expected)

    def refusal(scope: Scope, is_api: bool) -> Response | None:
        headers = Headers(scope=scope)
        host = headers.get("host")
        if host not in hosts:
            return _error(400, "BadRequest", "the Host header is not allowed")
        if scope["method"] in WRITE_METHODS and is_api and _is_write(scope, writes):
            return write_access(headers, host)
        if scope["method"] not in ALLOWED_METHODS:
            return _not_allowed(scope, writes)
        exchanged = login(scope)
        if exchanged is not None:
            return exchanged
        return api_access(headers, host) if is_api else None

    def login(scope: Scope) -> Response | None:
        """A read's ?token or ?launch: the cookie exchange, or a 401."""
        query = parse_qs(scope["query_string"].decode("latin-1"))
        offered = query.get("token")
        if offered is not None:
            if len(offered) == 1 and valid(offered[0]):
                return _exchange(scope["path"], cookie, token)
            return _error(401, "Unauthorized", "the token is not valid")
        launch = query.get("launch")
        if launch is not None:
            if len(launch) == 1 and launch_codes is not None:
                if launch_codes.redeem(launch[0]):
                    return _exchange(scope["path"], cookie, token)
            return _error(401, "Unauthorized", "the launch code is not valid")
        return None

    def write_access(headers: Headers, host: str | None) -> Response | None:
        if headers.get("origin") != f"http://{host}":
            return _error(
                403, "Forbidden", "a write needs the served Origin", write=True
            )
        presented = cookie_parser(headers.get("cookie", "")).get(cookie)
        if presented is None or not valid(presented):
            return _error(
                401, "Unauthorized", "a valid session cookie is required", write=True
            )
        media = headers.get("content-type", "").partition(";")[0].strip().lower()
        if media != JSON:
            return _error(
                415,
                "UnsupportedMediaType",
                "a write body must be application/json",
                write=True,
            )
        return None

    def api_access(headers: Headers, host: str | None) -> Response | None:
        origin = headers.get("origin")
        if origin is not None and origin != f"http://{host}":
            return _error(403, "Forbidden", "the Origin is not allowed")
        presented = cookie_parser(headers.get("cookie", "")).get(cookie)
        if presented is None or not valid(presented):
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


def _is_write(scope: Scope, writes: Sequence[BaseRoute]) -> bool:
    """Tell whether a write route matches the path and the method."""
    return any(route.matches(scope)[0] is Match.FULL for route in writes)


def _not_allowed(scope: Scope, writes: Sequence[BaseRoute]) -> Response:
    """405, naming the reads plus any write method the path takes."""
    allowed = list(ALLOWED_METHODS)
    for method in WRITE_METHODS:
        probe = {**scope, "method": method}
        if scope["path"].startswith("/api/") and _is_write(probe, writes):
            allowed.append(method)
    response = _error(405, "MethodNotAllowed", "the method is not allowed here")
    response.headers["allow"] = ", ".join(allowed)
    return response


def _exchange(path: str, cookie: str, token: str) -> Response:
    """Set the cookie and redirect to the same path without the query."""
    response = Response(status_code=303, headers={"location": _same_path(path)})
    response.headers["cache-control"] = "no-store"
    response.set_cookie(cookie, token, path="/", httponly=True, samesite="strict")
    return response


def _same_path(path: str) -> str:
    # "//host" or a backslash would make the redirect leave this origin.
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        return "/"
    return quote(path, safe="/")


def _error(
    status: int, error: str, message: str, *, write: bool = False
) -> JSONResponse:
    """A refusal; a write's carries the write routes' three-field body."""
    if write:
        body: BaseModel = WriteErrorOutput(error=error, message=message, details={})
    else:
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
