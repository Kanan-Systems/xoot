"""The fields a redaction may clear."""

from enum import StrEnum


class RedactableField(StrEnum):
    """
    Free-text fields a redaction may clear. Which entity allows which field
    is decided by the redaction service (e.g. only projects have a name).
    """

    TITLE = "title"
    BODY = "body"
    SUMMARY = "summary"
    NAME = "name"
