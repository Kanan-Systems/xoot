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
    goals = [
        (
            g.key,
            g.state,
            f"{g.batches_done} of {g.batches_total} done",
            str(g.open_backlog),
            clean(g.title),
        )
        for g in brief.open_goals
    ]
    blocked = [(b.key, str(b.open_backlog)) for b in brief.blocked]
    backlog = "  " + "  ".join(f"{lvl}: {n}" for lvl, n in brief.backlog_counts.items())
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
        "Open goals\n"
        + _rows(("key", "state", "batches", "backlog", "title"), goals)
        + (
            f"\n  (first {len(goals)} shown; more are open)"
            if brief.open_goals_truncated
            else ""
        ),
        "Active\n" + _items(brief.active),
        "Awaiting input\n" + _items(brief.awaiting_input),
        "Blocked by open backlog\n" + _rows(("key", "open backlog"), blocked),
        "Open backlog per level\n" + backlog,
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
