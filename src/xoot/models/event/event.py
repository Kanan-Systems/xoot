"""A stored event-log row."""

from xoot.models.event.new_event import NewEvent
from xoot.models.fields import Id, Timestamp


class Event(NewEvent):
    """
    One append-only audit record of a mutation, as stored.

    before/after hold only the fields that changed (a full snapshot for a
    create). For items and decisions they include the version, which is
    how version conflicts are explained. Item and decision creates store
    body_sha256 and body_len instead of the body. redacted_at is set when a
    redaction rewrote before/after.
    """

    id: Id
    redacted_at: Timestamp | None
