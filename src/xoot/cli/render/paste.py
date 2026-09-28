"""
The text forms of `xoot paste apply`: the plan on stderr and the receipt.

The plan is one line per op, then one indented line per disposition, field
change and carried descendant, then a SIDE EFFECTS section listing every
auto-backlog move. Each record the block creates, updates, disposes or moves
is named once per op with its kind and title (cut to TITLE_CUT characters;
every line is cleaned), so the user sees what they confirm. When a title or
body looks damaged by a clipboard code page, a POSSIBLE ENCODING DAMAGE
section follows, naming the op, key or ref and field, never the text. The
receipt is a fenced xoot-receipt block of keys and versions only; its info
string is not "xoot", so pasting it back into `xoot paste apply` finds no
block.
"""

from xoot.cli.render.text import clean
from xoot.cli.schemas.paste_receipt import PasteReceipt
from xoot.services.paste.models.paste_change import PasteChange
from xoot.services.paste.models.paste_encoding_warning import PasteEncodingWarning
from xoot.services.paste.models.paste_op_outcome import PasteOpOutcome
from xoot.services.paste.models.paste_result import PasteResult

RECEIPT_INFO = "xoot-receipt"
NONE = "-"
TITLE_CUT = 60
ENCODING_HEADING = "POSSIBLE ENCODING DAMAGE"
ENCODING_ADVICE = (
    'advice: a "?" between two letters is often a lost character; '
    "copy again using the UTF-8 command"
)
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
        lines.extend(_outcome_lines(result, outcome))
    lines.append("SIDE EFFECTS")
    if not result.auto_backlog:
        lines.append("  (none)")
    for move in result.auto_backlog:
        origin = move.origin_session or "an earlier session"
        lines.append(
            f"  {move.key}{_label(result, move.key)}: moves from the backlog of "
            f"{origin} to the project backlog"
        )
    return [clean(line) for line in lines]


def encoding_lines(warnings: tuple[PasteEncodingWarning, ...]) -> list[str]:
    """
    Describe the fields that look damaged, for the confirmation prompt.

    Args:
        - warnings (tuple[PasteEncodingWarning, ...]): from encoding_warnings.

    Returns:
        - lines (list[str]): the section, cleaned; empty when there is none.
    """
    if not warnings:
        return []
    lines = [ENCODING_HEADING]
    lines.extend(f"  op {w.index} {w.target} {w.field}" for w in warnings)
    lines.append(f"  {ENCODING_ADVICE}")
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


def _outcome_lines(result: PasteResult, outcome: PasteOpOutcome) -> list[str]:
    """The op line, then its dispositions, changes and carried keys."""
    key = outcome.key or NONE
    lines = [
        f"  op {outcome.index} {outcome.op}: {_target(outcome)}{_label(result, key)}"
    ]
    named = {key}
    for item_key, disposition in outcome.dispositions.items():
        lines.append(
            f"      dispose {item_key}{_label(result, item_key)}: {disposition}"
        )
        named.add(item_key)
    for change in outcome.changes:
        label = "" if change.key in named else _label(result, change.key)
        named.add(change.key)
        lines.append(f"      {_change(change, label)}")
    if outcome.carried:
        lines.append(f"      carries along: {', '.join(outcome.carried)}")
    return lines


def _label(result: PasteResult, key: str) -> str:
    """' goal "Title"', cut but not cleaned: plan_lines cleans whole lines."""
    label = result.labels.get(key)
    if label is None:
        return ""
    return f' {label.kind} "{label.title[:TITLE_CUT]}"'


def _target(outcome: PasteOpOutcome) -> str:
    key = outcome.key or NONE
    if not outcome.created:
        return key
    return f"{key} (new, ${outcome.ref})" if outcome.ref else f"{key} (new)"


def _change(change: PasteChange, label: str) -> str:
    if change.field in _TEXT_FIELDS:
        return f"{change.key}{label} {change.field}: changed"
    return (
        f"{change.key}{label} {change.field}: "
        f"{change.before or NONE} -> {change.after or NONE}"
    )
