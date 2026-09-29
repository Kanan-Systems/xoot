"""
db stats agrees with the real row counts and shows the schema version;
vacuum shrinks the freelist.
"""

from collections.abc import Callable
from typing import Any

from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services.redaction_service import redact_field
from xoot.store.migrator import latest_version
from xoot.store.store import Store


def test_stats_match_row_counts(
    xoot: Any, project: Project, make_item: Callable[..., Item], row_counts: Any
) -> None:
    """Every table's count equals a direct count(*)."""
    for _ in range(3):
        make_item(project, ItemKind.GOAL)
    stats = xoot("db", "stats", "--json").json()
    expected = {k: v for k, v in row_counts().items() if not k.startswith("sqlite_")}
    assert stats["rows"] == expected
    assert stats["rows"]["item"] == 3
    assert stats["page_count"] > stats["freelist_count"] >= 0
    text = xoot("db", "stats").out
    assert "item           3" in text


def test_stats_show_the_schema_version(xoot: Any) -> None:
    """Both output modes carry user_version and the newest known migration."""
    latest = latest_version()
    stats = xoot("db", "stats", "--json").json()
    assert stats["schema_version"] == latest
    assert stats["known_schema_version"] == latest
    text = xoot("db", "stats").out
    assert f"schema version: {latest} (latest known: {latest})\n" in text


def test_vacuum_after_deletes(
    xoot: Any,
    store: Store,
    project: Project,
    ctx: WriteContext,
    make_item: Callable[..., Item],
) -> None:
    """Redacted bodies free pages; vacuum brings freelist_count to zero."""
    items = [make_item(project, ItemKind.GOAL, body="v" * 30000) for _ in range(6)]
    for item in items:
        redact_field(store, "item", item.id, "body", ctx.actor)
    before = xoot("db", "stats", "--json").json()
    assert before["freelist_count"] > 0
    run = xoot("db", "vacuum", "--json")
    assert run.code == 0, run.err
    output = run.json()
    assert output["before"]["freelist_count"] == before["freelist_count"]
    assert output["after"]["freelist_count"] == 0
    assert output["after"]["rows"] == before["rows"]
    assert output["checkpointed"] is True
    assert "free pages: " in xoot("db", "vacuum").out
