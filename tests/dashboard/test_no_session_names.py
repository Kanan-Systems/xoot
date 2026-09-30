"""
The removed session concept is not in the dashboard API: no route path, and
no schema definition or property name, mentions it.
"""

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from xoot.dashboard.api import api_routes
from xoot.dashboard.export_schema import export

WORD = re.compile(r"session", re.IGNORECASE)


def _names(node: Any) -> Iterator[str]:
    """Every definition and property name, at any depth of the schema."""
    if isinstance(node, dict):
        for field in ("$defs", "properties"):
            yield from node.get(field, {})
        for value in node.values():
            yield from _names(value)
    elif isinstance(node, list):
        for value in node:
            yield from _names(value)


def test_no_route_or_schema_name_mentions_sessions(tmp_path: Path) -> None:
    """Route paths and schema names are the API's public vocabulary."""
    paths = [route.path for route in api_routes(tmp_path / "unused.db")]
    names = list(_names(json.loads(export())))
    assert "/api/v1/projects/{prefix}/tree" in paths
    assert {"TreeView", "project"} <= set(names)
    assert [p for p in paths if WORD.search(p)] == []
    assert [n for n in names if WORD.search(n)] == []
