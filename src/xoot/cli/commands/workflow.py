"""`xoot workflow`: export the active workflow as TOML, or import one."""

import argparse
from pathlib import Path

from xoot.cli import exit_codes
from xoot.cli.commands.common import WRITE, absolute, project_of
from xoot.cli.console import Console
from xoot.cli.render.results import plan_lines, render_export, render_import
from xoot.cli.schemas.workflow_export_output import WorkflowExportOutput
from xoot.cli.schemas.workflow_import_output import WorkflowImportOutput
from xoot.exceptions.workflow_file_error import WorkflowFileError
from xoot.exceptions.workflow_mapping_error import WorkflowMappingError
from xoot.models.workflow.workflow_change import WorkflowChange
from xoot.services.workflow_service import (
    get_active_workflow,
    plan_workflow_change,
    set_workflow,
)
from xoot.services.workflow_toml import dump_workflow, read_workflow_file
from xoot.store.store import Store

type StateMove = tuple[str, str, str]


def run_export(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Print the active workflow as TOML, or write it to -o FILE.

    Args:
        - args (argparse.Namespace): --project and --output.
        - store (Store): the database.
        - console (Console): output.

    Returns:
        - code (int): OK.

    Raises:
        - ProjectResolutionError: no project matched.
        - WorkflowFileError: the file could not be written.
    """
    project, _ = project_of(args, store)
    workflow = get_active_workflow(store, project.id)
    written_to = None
    if args.output is not None:
        path = Path(absolute(args.output))
        try:
            path.write_text(dump_workflow(workflow.definition), encoding="utf-8")
        except OSError as exc:
            raise WorkflowFileError("the workflow file could not be written") from exc
        written_to = str(path)
    output = WorkflowExportOutput(
        project=project.key_prefix,
        version=workflow.version,
        definition=workflow.definition,
        written_to=written_to,
    )
    console.result(output, render_export)
    return exit_codes.OK


def run_import(args: argparse.Namespace, store: Store, console: Console) -> int:
    """
    Replace the project's workflow with a TOML file, after confirmation.

    The change is planned first, so a missing mapping is refused before the
    prompt, and the prompt names the removed states and remap counts. A file
    identical to the active workflow prints "no changes" without asking.

    Args:
        - args (argparse.Namespace): the file, --project, --map and --yes.
        - store (Store): the database.
        - console (Console): output and the confirmation prompt.

    Returns:
        - code (int): OK.

    Raises:
        - ProjectResolutionError: no project matched.
        - WorkflowFileError: the file is unreadable, too large or not TOML.
        - pydantic.ValidationError: the file or a mapping is invalid.
        - WorkflowMappingError: an in-use removed state is not mapped, a
          mapping names a state the change keeps, or one is mapped twice.
        - ConfirmationError: the import was not confirmed.
    """
    project, _ = project_of(args, store)
    definition = read_workflow_file(Path(absolute(args.file)))
    change = WorkflowChange(definition=definition, mapping=_mapping(args.map))
    plan = plan_workflow_change(store, project.id, change)
    active = get_active_workflow(store, project.id)
    workflow = active
    if definition != active.definition:
        console.confirm(
            [
                f"import a new workflow into project {project.key_prefix}",
                *plan_lines(plan),
            ],
            args.yes,
        )
        workflow = set_workflow(store, project.id, change, WRITE)
    output = WorkflowImportOutput(
        project=project.key_prefix,
        version=workflow.version,
        changed=workflow.id != active.id,
        plan=plan,
    )
    console.result(output, render_import)
    return exit_codes.OK


def parse_move(text: str) -> StateMove:
    """
    Split a --map value "kind:old=new" into its three parts.

    Args:
        - text (str): the option value.

    Returns:
        - move (StateMove): (kind, old state, new state), not yet validated.

    Raises:
        - argparse.ArgumentTypeError: the value is not kind:old=new.
    """
    kind, colon, rest = text.partition(":")
    old, equals, new = rest.partition("=")
    if not (kind and colon and old and equals and new):
        raise argparse.ArgumentTypeError("expected kind:old=new")
    return kind, old, new


def _mapping(moves: list[StateMove]) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {}
    for kind, old, new in moves:
        if old in mapping.setdefault(kind, {}):
            raise WorkflowMappingError("a state is mapped more than once")
        mapping[kind][old] = new
    return mapping
