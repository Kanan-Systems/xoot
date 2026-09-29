"""The Claude Code plugin and its marketplace entry are well formed."""

import json
import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugin"
SKILL = PLUGIN / "skills" / "xoot-workflow" / "SKILL.md"


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _frontmatter(text: str) -> dict[str, str]:
    """The `key: value` lines between the leading pair of --- lines."""
    lines = text.splitlines()
    assert lines[0] == "---", "no frontmatter"
    end = lines.index("---", 1)
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(": ")
        assert sep and key and value.strip(), f"not a key: value line: {line!r}"
        assert key not in fields, f"duplicate key {key}"
        fields[key] = value.strip()
    return fields


def test_plugin_manifest_matches_package() -> None:
    """plugin.json parses and its version is the package's version."""
    manifest = _json(PLUGIN / ".claude-plugin" / "plugin.json")
    declared = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert manifest["name"] == "xoot"
    assert manifest["version"] == version("xoot") == declared["project"]["version"]
    assert manifest["author"] == {"name": "Kanan Systems"}
    assert manifest["license"] == "MIT"
    assert manifest["description"] and manifest["keywords"]


def test_mcp_config_runs_installed_server() -> None:
    """.mcp.json starts the installed xoot-mcp, with no arguments."""
    assert _json(PLUGIN / ".mcp.json") == {"xoot": {"command": "xoot-mcp", "args": []}}


def test_marketplace_lists_the_plugin() -> None:
    """The marketplace's one entry points at plugin/ and names it xoot."""
    marketplace = _json(REPO / ".claude-plugin" / "marketplace.json")
    (entry,) = marketplace["plugins"]
    assert entry["name"] == "xoot"
    assert (REPO / entry["source"]).resolve() == PLUGIN
    assert marketplace["owner"] == {"name": "Kanan Systems"}


def test_skill_frontmatter_parses() -> None:
    """SKILL.md has a name matching its directory and a description."""
    fields = _frontmatter(SKILL.read_text(encoding="utf-8"))
    assert fields.keys() == {"name", "description"}
    assert fields["name"] == SKILL.parent.name
