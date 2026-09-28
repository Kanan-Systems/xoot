"""db_stats reports the real counts; vacuum frees the free pages."""

import os
from collections.abc import Callable

from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services.redaction_service import redact_field
from xoot.services.stats_service import db_stats
from xoot.store.migrator import latest_version, user_version
from xoot.store.store import Store

BIG = "b" * 30000


def free_pages(
    store: Store, project: Project, ctx: WriteContext, make_item: Callable[..., Item]
) -> None:
    """Create large bodies and redact them, leaving their pages free."""
    items = [make_item(project, ItemKind.GOAL, body=BIG) for _ in range(8)]
    for item in items:
        redact_field(store, "item", item.id, "body", ctx.actor)


def test_stats_match_the_database(
    store: Store,
    project: Project,
    make_item: Callable[..., Item],
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """Row counts, page counts and file sizes agree with direct reads."""
    make_item(project, ItemKind.GOAL)
    stats = db_stats(store)
    # SQLite's own bookkeeping (sqlite_sequence) is not reported.
    tables = {k: v for k, v in row_counts().items() if not k.startswith("sqlite_")}
    assert stats.rows == tables
    assert stats.db_bytes == os.stat(store.path).st_size
    assert stats.wal_bytes == os.stat(f"{store.path}-wal").st_size
    page_size = store.conn.execute("PRAGMA page_size").fetchone()[0]
    assert store.checkpoint()
    assert db_stats(store).page_count * page_size == os.stat(store.path).st_size


def test_vacuum_shrinks_the_freelist(
    store: Store, project: Project, ctx: WriteContext, make_item: Callable[..., Item]
) -> None:
    """After deletes, vacuum leaves no free page and an empty WAL."""
    free_pages(store, project, ctx, make_item)
    before = db_stats(store)
    assert before.freelist_count > 0
    assert store.vacuum()
    after = db_stats(store)
    assert after.freelist_count == 0
    assert after.page_count < before.page_count
    assert after.rows == before.rows
    assert os.stat(f"{store.path}-wal").st_size == 0


def test_stats_report_the_schema_version(store: Store) -> None:
    """The DB's user_version and the newest known migration, read separately."""
    stats = db_stats(store)
    assert stats.schema_version == user_version(store.conn) == latest_version()
    assert stats.known_schema_version == latest_version()
    store.conn.execute("PRAGMA user_version = 0")
    behind = db_stats(store)
    assert behind.schema_version == 0
    assert behind.known_schema_version == latest_version()
