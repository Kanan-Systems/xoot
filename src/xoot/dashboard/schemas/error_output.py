"""The body of every dashboard API error."""

from pydantic import BaseModel, ConfigDict


class ErrorOutput(BaseModel):
    """
    The error class name and a safe message, built by the same rules as MCP
    tool errors: never driver text, SQL or an arbitrary input value.
    """

    model_config = ConfigDict(frozen=True)

    error: str
    message: str
