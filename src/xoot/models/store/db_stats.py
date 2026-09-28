"""A snapshot of the database file's size and contents."""

from pydantic import BaseModel, ConfigDict, Field


class DbStats(BaseModel):
    """
    Page counts from SQLite, the on-disk sizes of the database and its WAL
    in bytes (0 for a WAL that does not exist), the row count of every
    table by name, and the schema version: the database's user_version
    beside the newest migration this code ships.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    page_count: int = Field(ge=0)
    freelist_count: int = Field(ge=0)
    db_bytes: int = Field(ge=0)
    wal_bytes: int = Field(ge=0)
    rows: dict[str, int]
    schema_version: int = Field(ge=0)
    known_schema_version: int = Field(ge=0)
