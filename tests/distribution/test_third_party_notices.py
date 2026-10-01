"""
THIRD_PARTY_NOTICES.md lists exactly the packages the lockfiles pin for a
shipped or running xoot: the Python runtime closure in uv.lock and the
production npm packages in package-lock.json (those holding only type
declarations named as not bundled). Reads the lockfiles only, so it runs
without node_modules.
"""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]
NOTICES = REPO / "src" / "xoot" / "THIRD_PARTY_NOTICES.md"
_ROW = re.compile(r"^\| (\S+) \| (\S+) \|")
_PAIR = re.compile(r"(\S+) (\d\S*?)(?:,|\.$)")


@pytest.fixture(name="generator", scope="module")
def fixture_generator() -> ModuleType:
    """scripts/gen_notices.py, loaded from its path (scripts is no package)."""
    spec = importlib.util.spec_from_file_location(
        "gen_notices", REPO / "scripts" / "gen_notices.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _section(text: str, heading: str) -> str:
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


def _rows(section: str) -> dict[str, str]:
    rows = {}
    for line in section.splitlines():
        match = _ROW.match(line)
        if match is not None and match.group(1) not in ("Package", "---|---|---|---|"):
            rows[match.group(1)] = match.group(2)
    return rows


def test_python_packages_match_uv_lock(generator: ModuleType) -> None:
    """Every runtime package and version in uv.lock, nothing else."""
    text = NOTICES.read_text(encoding="utf-8")
    listed = _rows(_section(text, "## Python packages"))
    assert listed == generator.python_locked()
    assert "pywin32" not in listed and "httpx2-jsfetch" not in listed


def test_npm_packages_match_package_lock(generator: ModuleType) -> None:
    """Bundled rows plus the named type-only packages are the production set."""
    section = _section(NOTICES.read_text(encoding="utf-8"), "## JavaScript packages")
    bundled = _rows(section)
    tail = " ".join(section.split("not listed above:", 1)[1].split())
    declarations = dict(_PAIR.findall(tail))
    assert not set(bundled) & set(declarations)
    assert {**bundled, **declarations} == generator.npm_locked()
    assert all(name.startswith("@types/") or name == "csstype" for name in declarations)


def test_every_bundled_package_has_a_license_text(generator: ModuleType) -> None:
    """Each listed package appears under a license text, or is named as bare."""
    text = NOTICES.read_text(encoding="utf-8")
    users = " ".join(re.findall(r"^Used by: (.*)$", text, re.MULTILINE))
    bare = _section(text, "## Packages without a license file")
    locked = {**generator.python_locked()}
    for name, version in locked.items():
        assert f"{name} {version}" in users or f"{name} {version}:" in bare


@pytest.mark.parametrize(
    ("marker", "holds"),
    [
        ("sys_platform == 'win32'", False),
        ("sys_platform != 'emscripten'", True),
        ("python_full_version < '3.13'", True),
        ("python_full_version < '3.12'", False),
        (
            "implementation_name != 'PyPy' and platform_python_implementation != 'PyPy'",
            True,
        ),
        ("sys_platform == 'win32' or sys_platform == 'linux'", True),
    ],
)
def test_markers(generator: ModuleType, marker: str, holds: bool) -> None:
    """The marker forms uv.lock uses, for CPython 3.12 on Linux."""
    env = {
        "sys_platform": "linux",
        "platform_python_implementation": "CPython",
        "implementation_name": "cpython",
        "python_full_version": "3.12",
    }
    assert generator.marker_holds(marker, env) is holds


def test_unknown_marker_is_refused(generator: ModuleType) -> None:
    """A marker form the evaluator does not know fails loudly."""
    with pytest.raises(ValueError, match="unsupported marker"):
        generator.marker_holds("extra == 'x'", {"sys_platform": "linux"})
