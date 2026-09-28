"""A text field of a paste block that a clipboard code page may have damaged."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class PasteEncodingWarning(BaseModel):
    """
    Names where a "?" sits between two letters: the op by its 1-based index,
    the record it creates or targets (a key, a $ref, or "-" when it names
    neither) and the field. Never the text itself, which is stored data.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int
    target: str
    field: Literal["title", "body"]
