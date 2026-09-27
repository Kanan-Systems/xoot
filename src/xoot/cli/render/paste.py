"""
The text forms of `xoot paste apply`: the plan on stderr and the receipt.

The plan is one line per op, then one indented line per field change and
carried descendant, then a SIDE EFFECTS section listing every auto-backlog
move. The receipt is a fenced xoot-receipt block holding JSON; its info
string is not "xoot", so pasting it back into `xoot paste apply` finds no
block. Neither ever shows a title or body.
"""

from xoot.cli.render.text import clean
from xoot.cli.schemas.paste_receipt import PasteReceipt
from xoot.services.paste.models.paste_change import PasteChange
from xoot.services.paste.models.paste_op_outcome import PasteOpOutcome
from xoot.services.paste.models.paste_result import PasteResult

RECEIPT_INFO = "xoot-receipt"
NONE = "-"
# Stored text: a plan names the field, never its value.
_TEXT_FIELDS = frozenset({"title", "body", "summary"})


def plan_lines(result: PasteResult) -> list[str]:
    """
    Describe a dry run for the confirmation prompt.

    Args:
        - result (PasteResult): the dry run's result.

    Returns:
        - lines (list[str]): the plan, cleaned, one entry per line.
    """
    lines = [
        f"paste plan: project {result.project}, session {result.session} "
        f"({result.session_status} after the block)"
    ]
    for outcome in result.outcomes:
        lines.append(f"  op {outcome.index} {outcome.op}: {_target(outcome)}")
        lines.extend(f"      {_change(change)}" for change in outcome.changes)
        if outcome.carried:
            lines.append(f"      carries along: {', '.join(outcome.carried)}")
    lines.append("SIDE EFFECTS")
    if not result.auto_backlog:
        lines.append("  (none)")
    for move in result.auto_backlog:
        origin = move.origin_session or "an earlier session"
        lines.append(
            f"  {move.key}: moves from the backlog of {origin} to the project backlog"
        )
    return [clean(line) for line in lines]


def receipt(result: PasteResult) -> PasteReceipt:
    """
    Reduce an applied result to its receipt.

    Args:
        - result (PasteResult): the apply's result.

    Returns:
        - receipt (PasteReceipt): session, refs and final records.
    """
    return PasteReceipt(
        project=result.project,
        session=result.session,
        session_status=result.session_status,
        refs=dict(result.refs),
        items=list(result.items),
        decisions=list(result.decisions),
    )


def render_receipt(result: PasteResult) -> str:
    """
    Render the receipt as a fenced xoot-receipt block.

    Args:
        - result (PasteResult): the apply's result.

    Returns:
        - text (str): the fenced JSON block.
    """
    body = receipt(result).model_dump_json(indent=2)
    return f"```{RECEIPT_INFO}\n{body}\n```"


def _target(outcome: PasteOpOutcome) -> str:
    key = outcome.key or NONE
    if not outcome.created:
        return key
    return f"{key} (new, ${outcome.ref})" if outcome.ref else f"{key} (new)"


def _change(change: PasteChange) -> str:
    if change.field in _TEXT_FIELDS:
        return f"{change.key} {change.field}: changed"
    return (
        f"{change.key} {change.field}: "
        f"{change.before or NONE} -> {change.after or NONE}"
    )
