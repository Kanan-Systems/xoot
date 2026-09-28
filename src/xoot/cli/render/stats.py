"""The text forms of `xoot db stats` and `xoot db vacuum`."""

from xoot.cli.render.text import clean, table
from xoot.cli.schemas.vacuum_output import VacuumOutput
from xoot.models.store.db_stats import DbStats


def render_stats(stats: DbStats) -> str:
    """
    Render database statistics.

    Args:
        - stats (DbStats): the statistics.

    Returns:
        - text (str): the schema version, file sizes, page counts and a
          row-count table.
    """
    rows = [(name, str(count)) for name, count in stats.rows.items()]
    return "\n".join(
        [
            f"database: {clean(stats.path)}",
            f"schema version: {stats.schema_version}"
            f" (latest known: {stats.known_schema_version})",
            f"db bytes: {stats.db_bytes}",
            f"wal bytes: {stats.wal_bytes}",
            f"pages: {stats.page_count}",
            f"free pages: {stats.freelist_count}",
            "",
            table(("TABLE", "ROWS"), rows),
        ]
    )


def render_vacuum(output: VacuumOutput) -> str:
    """
    Render a vacuum's before and after figures.

    Args:
        - output (VacuumOutput): the vacuum result.

    Returns:
        - text (str): sizes and page counts, before -> after.
    """
    before, after = output.before, output.after
    return "\n".join(
        [
            f"database: {clean(after.path)}",
            f"db bytes: {before.db_bytes} -> {after.db_bytes}",
            f"pages: {before.page_count} -> {after.page_count}",
            f"free pages: {before.freelist_count} -> {after.freelist_count}",
            f"wal truncated: {'yes' if output.checkpointed else 'no'}",
        ]
    )
