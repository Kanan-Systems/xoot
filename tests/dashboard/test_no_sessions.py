"""
The dashboard carries no trace of the removed session concept: no
component, route, type, style or test in dashboard/src, and no module of
src/xoot/dashboard, mentions sessions. The HTTP login cookie and token keep
their standard names, which are the only allowed uses of the word.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCANNED = (
    (ROOT / "dashboard" / "src", ("*.ts", "*.tsx", "*.css", "*.json")),
    (ROOT / "src" / "xoot" / "dashboard", ("*.py", "*.html")),
)
WORD = re.compile(r"session", re.IGNORECASE)
# The browser's login credential, not the tracker concept.
ALLOWED = re.compile(r"session (cookie|token)", re.IGNORECASE)


def _files() -> list[Path]:
    found = [
        path
        for base, patterns in SCANNED
        for pattern in patterns
        for path in base.rglob(pattern)
    ]
    return sorted(found)


def test_the_scan_covers_both_trees() -> None:
    """The scan sees the components, the API modules and the schema."""
    names = {path.name for path in _files()}
    assert {"App.tsx", "TreePage.tsx", "schema.json", "api.py"} <= names


@pytest.mark.parametrize("path", _files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_session_reference(path: Path) -> None:
    """Only the login cookie and token may use the word."""
    text = ALLOWED.sub("", path.read_text(encoding="utf-8"))
    hits = [
        f"{number}: {line.strip()}"
        for number, line in enumerate(text.splitlines(), 1)
        if WORD.search(line)
    ]
    assert not hits, hits
