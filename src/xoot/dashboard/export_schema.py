"""
Export the dashboard API's response and request models as one JSON Schema
document.

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

from xoot.dashboard.requests.capture_request import CaptureRequest
from xoot.dashboard.requests.cover_request import CoverRequest
from xoot.dashboard.requests.decision_create_request import DecisionCreateRequest
from xoot.dashboard.requests.decision_update_request import DecisionUpdateRequest
from xoot.dashboard.requests.item_create_request import ItemCreateRequest
from xoot.dashboard.requests.item_update_request import ItemUpdateRequest
from xoot.dashboard.requests.move_request import MoveRequest
from xoot.dashboard.requests.project_rename_request import ProjectRenameRequest
from xoot.dashboard.requests.push_request import PushRequest
from xoot.dashboard.schemas.backlog_view import BacklogView
from xoot.dashboard.schemas.brief_view import BriefView
from xoot.dashboard.schemas.changes_view import ChangesView
from xoot.dashboard.schemas.decision_view import DecisionView
from xoot.dashboard.schemas.decisions_view import DecisionsView
from xoot.dashboard.schemas.error_output import ErrorOutput
from xoot.dashboard.schemas.item_view import ItemView
from xoot.dashboard.schemas.meta_output import MetaOutput
from xoot.dashboard.schemas.project_info import ProjectInfo
from xoot.dashboard.schemas.projects_output import ProjectsOutput
from xoot.dashboard.schemas.tree_view import TreeView
from xoot.dashboard.schemas.workflow_view import WorkflowView
from xoot.dashboard.schemas.write_error_output import WriteErrorOutput
from xoot.server.schemas.cover_output import CoverOutput
from xoot.server.schemas.decision_write_output import DecisionOutput
from xoot.server.schemas.item_update_output import ItemUpdateOutput
from xoot.server.schemas.item_write_output import ItemWriteOutput
from xoot.server.schemas.push_output import PushOutput

# Only meaningful in a source checkout: <repo>/src/xoot/dashboard/ -> <repo>.
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "dashboard/src/api/schema.json"

RESPONSES: tuple[type[BaseModel], ...] = (
    BacklogView, BriefView, ChangesView, CoverOutput, DecisionOutput,
    DecisionView, DecisionsView, ErrorOutput, ItemUpdateOutput, ItemView,
    ItemWriteOutput, MetaOutput, ProjectInfo, ProjectsOutput, PushOutput,
    TreeView, WorkflowView, WriteErrorOutput,
)  # fmt: skip
# Write bodies, exported as the server validates them.
REQUESTS: tuple[type[BaseModel], ...] = (
    CaptureRequest, CoverRequest, DecisionCreateRequest, DecisionUpdateRequest,
    ItemCreateRequest, ItemUpdateRequest, MoveRequest, ProjectRenameRequest,
    PushRequest,
)  # fmt: skip


def export() -> str:
    """
    Render every response and request model into one schema document.

    Returns:
        - text (str): the JSON document, keys sorted, newline-terminated.
    """
    _, schema = models_json_schema(
        [
            *((model, "serialization") for model in RESPONSES),
            *((model, "validation") for model in REQUESTS),
        ],
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
