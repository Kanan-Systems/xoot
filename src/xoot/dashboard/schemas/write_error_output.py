"""The body of every dashboard write error."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class WriteErrorOutput(BaseModel):
    """
    A write error: the class name and safe message of ErrorOutput plus
    details, always present. details is an empty object when there is
    nothing to report, or structured facts such as a version conflict's
    current version, changed fields and actors. A separate model, because
    read errors keep their two-field body.
    """

    model_config = ConfigDict(frozen=True)

    error: str
    message: str
    details: dict[str, Any]
