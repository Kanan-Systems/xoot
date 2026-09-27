"""One field change a paste op made, as the plan shows it."""

from pydantic import BaseModel, ConfigDict


class PasteChange(BaseModel):
    """
    A field of one record changing. before and after are state or status
    names, or keys for references; for title, body and summary they are
    always None, so a plan never carries stored text.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    field: str
    before: str | None
    after: str | None
