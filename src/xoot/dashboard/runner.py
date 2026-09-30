"""
Serving the dashboard in the foreground.

The socket is bound here, before uvicorn starts, so a port in use fails
fast with a clear message, and the browser can be opened once the socket
already queues connections. Uvicorn runs with its access log off, since
request lines would carry the token, and at warning level. --open hands the
browser opener a one-time launch code, never the session token: an
opener's argv is readable by every local user.
"""

import errno
import secrets
import socket
import sys
from pathlib import Path

import uvicorn

from xoot.dashboard.app import create_app
from xoot.dashboard.browser import open_url
from xoot.dashboard.launch_codes import LaunchCodes
from xoot.dashboard.ports import DEFAULT_PORT

HOST = "127.0.0.1"
__all__ = ["DEFAULT_PORT", "PortUnavailableError", "bind", "serve"]


class PortUnavailableError(OSError):
    """The port could not be bound: in use, or not permitted."""


def bind(port: int) -> socket.socket:
    """
    Bind and listen on 127.0.0.1:<port>.

    Args:
        - port (int): the TCP port.

    Returns:
        - sock (socket.socket): a listening socket.

    Raises:
        - PortUnavailableError: the port is in use or may not be bound.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((HOST, port))
        sock.listen()
    except OSError as exc:
        sock.close()
        reason = "in use" if exc.errno == errno.EADDRINUSE else "not available"
        raise PortUnavailableError(exc.errno, f"port {port} is {reason}") from exc
    return sock


def dashboard_url(port: int, token: str) -> str:
    """
    Build the URL the user opens; the query hands the token to the browser.

    Args:
        - port (int): the served port.
        - token (str): the per-launch token.

    Returns:
        - url (str): http://xoot.localhost:<port>/?token=<token>.
    """
    return f"http://xoot.localhost:{port}/?token={token}"


def launch_url(port: int, code: str) -> str:
    """
    Build the URL handed to the browser opener.

    Args:
        - port (int): the served port.
        - code (str): a one-time launch code.

    Returns:
        - url (str): http://xoot.localhost:<port>/?launch=<code>.
    """
    return f"http://xoot.localhost:{port}/?launch={code}"


def serve(db_path: Path, sock: socket.socket, open_browser: bool) -> None:
    """
    Print the URL once, optionally open it, and serve until interrupted.

    The token lives only in memory and in that one stdout line: it is not
    logged and not written to disk.

    Args:
        - db_path (Path): the database file.
        - sock (socket.socket): the listening socket from bind().
        - open_browser (bool): also open the URL in a browser.
    """
    port = sock.getsockname()[1]
    token = secrets.token_urlsafe(32)
    codes = LaunchCodes()
    print(dashboard_url(port, token), file=sys.stdout, flush=True)
    print(
        f"serving on {HOST}:{port}; Ctrl+C stops",
        file=sys.stderr,
        flush=True,
    )
    if open_browser and not open_url(launch_url(port, codes.issue())):
        print(
            "warning: could not open a browser; open the URL above",
            file=sys.stderr,
            flush=True,
        )
    config = uvicorn.Config(
        create_app(db_path, token, port, launch_codes=codes),
        log_level="warning",
        access_log=False,
        lifespan="off",
        ws="none",
        proxy_headers=False,
        server_header=False,
    )
    try:
        uvicorn.Server(config).run(sockets=[sock])
    except KeyboardInterrupt:
        # Uvicorn re-raises the captured SIGINT once it has shut down.
        pass
    finally:
        sock.close()
