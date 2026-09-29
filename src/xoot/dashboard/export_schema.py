"""
Export the dashboard API's response models as one JSON Schema document.

`python -m xoot.dashboard.export_schema` writes it to the frontend's
dashboard/src/api/schema.json (or --output), from which the TypeScript types
are generated. Keys are sorted, so an unchanged API exports byte for byte
the same file and a test can compare the committed copy.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from xoot.dashboard.schemas.backlogs_view import BacklogsView
from xoot.dashboard.schemas.brief_view import BriefView
from xoot.dashboard.schemas.changes_view import ChangesView
from xoot.dashboard.schemas.decision_view import DecisionView
from xoot.dashboard.schemas.decisions_view import DecisionsView
from xoot.dashboard.schemas.error_output import ErrorOutput
from xoot.dashboard.schemas.item_view import ItemView
from xoot.dashboard.schemas.meta_output import MetaOutput
from xoot.dashboard.schemas.projects_output import ProjectsOutput
from xoot.dashboard.schemas.session_view import SessionView
from xoot.dashboard.schemas.sessions_view import SessionsView
from xoot.dashboard.schemas.tree_view import TreeView

# Only meaningful in a source checkout: <repo>/src/xoot/dashboard/ -> <repo>.
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "dashboard/src/api/schema.json"

RESPONSES: tuple[type[BaseModel], ...] = (
    BacklogsView, BriefView, ChangesView, DecisionView, DecisionsView,
    ErrorOutput, ItemView, MetaOutput, ProjectsOutput, SessionView,
    SessionsView, TreeView,
)  # fmt: skip


def export() -> str:
    """
    Render every response model into one schema document.

    Returns:
        - text (str): the JSON document, keys sorted, newline-terminated.
    """
    _, schema = models_json_schema(
        [(model, "serialization") for model in RESPONSES],
        title="XootDashboardApi",
    )
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """
    Write the schema document.

    Args:
        - argv (Sequence[str] | None): arguments; sys.argv[1:] when None.

    Returns:
        - code (int): 0.
    """
    parser = argparse.ArgumentParser(
        prog="python -m xoot.dashboard.export_schema",
        description="Write the dashboard API JSON Schema.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="file to write (default: dashboard/src/api/schema.json)",
    )
    args = parser.parse_args(argv)
    args.output.write_text(export(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
