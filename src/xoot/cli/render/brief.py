"""The text form of `xoot brief`: one titled section per part of the brief."""

from xoot.cli.render.projects import project_lines
from xoot.cli.render.text import clean, table
from xoot.server.schemas.brief_output import BriefOutput
from xoot.server.schemas.item_summary import ItemSummary

NONE = "  (none)"


def render_brief(brief: BriefOutput) -> str:
    """
    Render a brief as sections separated by blank lines.

    Args:
        - brief (BriefOutput): the brief.

    Returns:
        - text (str): the sections.
    """
    counts = "  " + "  ".join(f"{c}: {n}" for c, n in brief.counts.items())
    sessions = [
        (s.key, clean(s.title), s.client, s.started_at) for s in brief.open_sessions
    ]
    decisions = [(d.key, d.status, clean(d.title)) for d in brief.recent_decisions]
    workflow = [
        f"  {kind}: "
        + ", ".join(f"{s.name} ({s.category})" for s in entry.states)
        + (" [transitions restricted]" if entry.transitions_restricted else "")
        for kind, entry in brief.workflow.items()
    ]
    sections = [
        "\n".join([*project_lines(brief.project), f"resolved by: {brief.resolved_by}"]),
        brief.header,
        "Counts\n" + counts,
        "Open sessions\n"
        + _rows(("key", "title", "client", "started"), sessions)
        + (
            f"\n  (first {len(sessions)} shown; more are open)"
            if brief.open_sessions_truncated
            else ""
        ),
        "Active\n" + _items(brief.active),
        "Awaiting input\n" + _items(brief.awaiting_input),
        "Pending session backlog\n" + _items(brief.pending_session_backlog),
        f"Project backlog: {brief.project_backlog_count}",
        "Open session backlog\n"
        + _items(brief.open_session_backlog)
        + (
            f"\n  (first {len(brief.open_session_backlog)} shown; more are held)"
            if brief.open_session_backlog_truncated
            else ""
        ),
        "Recent decisions\n" + _rows(("key", "status", "title"), decisions),
        "Workflow\n" + "\n".join(workflow),
    ]
    return "\n\n".join(sections)


def _items(items: list[ItemSummary]) -> str:
    rows = [(i.key, i.kind, i.state, clean(i.title)) for i in items]
    return _rows(("key", "kind", "state", "title"), rows)


def _rows(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    if not rows:
        return NONE
    return "\n".join("  " + line for line in table(headers, rows).splitlines())
