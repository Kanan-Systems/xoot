"""The --open helper: wslview under WSL, Python's webbrowser elsewhere."""

import subprocess
import webbrowser
from typing import Any

import pytest

from xoot.dashboard import browser

URL = "http://xoot.localhost:7373/?token=t"


def test_wsl_uses_wslview(monkeypatch: pytest.MonkeyPatch) -> None:
    """Under WSL the URL goes to wslview, as its only argument."""
    calls: list[list[str]] = []

    def run(argv: list[str], **kwargs: Any) -> None:
        assert kwargs["check"] is True
        calls.append(argv)

    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(webbrowser, "open", _forbidden)
    assert browser.open_url(URL) is True
    assert calls == [["wslview", URL]]


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError(2, "no wslview"),
        subprocess.CalledProcessError(1, "wslview"),
        subprocess.TimeoutExpired("wslview", 15),
    ],
)
def test_wsl_failures_return_false(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    """A missing, failing or hanging wslview is reported, not raised."""

    def run(argv: list[str], **kwargs: Any) -> None:
        assert argv and kwargs
        raise failure

    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.setattr(subprocess, "run", run)
    assert browser.open_url(URL) is False


@pytest.mark.parametrize("result", [True, False])
def test_elsewhere_webbrowser_is_used(
    monkeypatch: pytest.MonkeyPatch, result: bool
) -> None:
    """Without WSL, webbrowser.open decides."""
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(webbrowser, "open", lambda url: result and url == URL)
    assert browser.open_url(URL) is result


def test_a_webbrowser_error_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """webbrowser.Error is reported, not raised."""

    def broken(url: str) -> bool:
        raise webbrowser.Error(url)

    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.setattr(webbrowser, "open", broken)
    assert browser.open_url(URL) is False


def _forbidden(*args: Any, **kwargs: Any) -> None:
    raise AssertionError((args, kwargs))
