"""The text form of `xoot backlog`: items grouped by what they sit on."""

from xoot.cli.render.text import clean
from xoot.server.schemas.backlog_output import BacklogOutput

INDENT = "  "


def render_backlog(output: BacklogOutput) -> str:
    """
    Render backlog items under a heading per holder, in list order.

    The project backlog comes first, then each goal's or batch's own, as
    backlog_list orders them. Each line shows the key, the state with its
    category, the title and the item it was found on.

    Args:
        - output (BacklogOutput): the list.

    Returns:
        - text (str): the grouped lines, or "(no backlog)".
    """
    if not output.items:
        return "(no backlog)"
    lines: list[str] = []
    holder: object = object()
    for entry in output.items:
        if entry.parent != holder:
            holder = entry.parent
            heading = "project" if entry.parent is None else f"on {entry.parent}"
            lines.append(f"{heading} ({entry.level} backlog)")
        found = "" if entry.found_on is None else f"  (found on {entry.found_on})"
        state = f"{entry.state} ({entry.category or 'unknown'})"
        lines.append(f"{INDENT}{entry.key}  {state}  {clean(entry.title)}{found}")
    return "\n".join(lines)
