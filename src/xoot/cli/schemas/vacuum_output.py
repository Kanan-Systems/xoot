"""What `xoot db vacuum` reports."""

from pydantic import BaseModel, ConfigDict

from xoot.models.store.db_stats import DbStats


class VacuumOutput(BaseModel):
    """
    Statistics before and after the rebuild, and whether the final
    checkpoint emptied the WAL.
    """

    model_config = ConfigDict(frozen=True)

    before: DbStats
    after: DbStats
    checkpointed: bool
