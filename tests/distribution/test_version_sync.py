"""
One release version everywhere it is written by hand: pyproject.toml, the
plugin manifest, the top CHANGELOG entry and the README status line.
"""

import json
import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RELEASE = "1.0.0"


def _versions() -> dict[str, str]:
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    plugin = json.loads(
        (REPO / "plugin" / ".claude-plugin" / "plugin.json").read_text("utf-8")
    )
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    top = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    status = re.search(r"^Status: (\d+\.\d+\.\d+)\b", readme, re.MULTILINE)
    assert top is not None, "CHANGELOG.md has no version entry"
    assert status is not None, "README.md has no status line"
    return {
        "pyproject.toml": pyproject["project"]["version"],
        "plugin.json": plugin["version"],
        "CHANGELOG.md": top.group(1),
        "README.md": status.group(1),
    }


def test_every_file_names_the_release() -> None:
    """A release bump that misses one of the four files fails here."""
    assert _versions() == dict.fromkeys(_versions(), RELEASE)


def test_changelog_top_entry_is_the_newest() -> None:
    """Entries run newest first, so the top one is the release."""
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    found = re.findall(r"^## \[(\d+)\.(\d+)\.(\d+)\]", changelog, re.MULTILINE)
    versions = [tuple(int(part) for part in entry) for entry in found]
    assert versions == sorted(versions, reverse=True)
    assert len(versions) == len(set(versions))
