"""The text forms of write results: workflow export and import, redaction."""

from xoot.cli.render.text import clean
from xoot.cli.schemas.workflow_export_output import WorkflowExportOutput
from xoot.cli.schemas.workflow_import_output import WorkflowImportOutput
from xoot.models.event.redaction_result import RedactionResult
from xoot.models.workflow.workflow_plan import WorkflowPlan
from xoot.services.workflow_toml import dump_workflow


def render_export(output: WorkflowExportOutput) -> str:
    """
    Render an export: the TOML itself, or where it was written.

    Args:
        - output (WorkflowExportOutput): the export.

    Returns:
        - text (str): the TOML document, or a one-line note.
    """
    if output.written_to is None:
        return dump_workflow(output.definition).rstrip("\n")
    return (
        f"wrote {output.project} workflow version {output.version} "
        f"to {clean(output.written_to)}"
    )


def render_import(output: WorkflowImportOutput) -> str:
    """
    Render an applied import.

    Args:
        - output (WorkflowImportOutput): the import.

    Returns:
        - text (str): the new version and what it changed.
    """
    return "\n".join(
        [f"{output.project} workflow is now version {output.version}"]
        + plan_lines(output.plan)
    )


def plan_lines(plan: WorkflowPlan) -> list[str]:
    """
    Describe a workflow change: removed states and item rewrites per kind.

    Args:
        - plan (WorkflowPlan): the change.

    Returns:
        - lines (list[str]): one line per kind for each part.
    """
    removed = [
        f"  {kind}: {', '.join(states) or '(none)'}"
        for kind, states in plan.removed.items()
    ]
    remaps = [f"  {kind}: {count}" for kind, count in plan.remaps.items()]
    return ["removed states:", *removed, "items remapped:", *remaps]


def render_redaction(result: RedactionResult, key: str) -> str:
    """
    Render a redaction without any content.

    Args:
        - result (RedactionResult): the redaction.
        - key (str): the public key the user named.

    Returns:
        - text (str): what was redacted and how many events were rewritten.
    """
    version = "" if result.version is None else f", now version {result.version}"
    count = len(result.redacted_event_ids)
    events = "1 event" if count == 1 else f"{count} events"
    return (
        f"redacted {result.field} of {result.entity_type} {key}{version}; "
        f"{events} rewritten"
    )
