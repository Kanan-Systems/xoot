"""A stored event-log row."""

from xoot.models.event.new_event import NewEvent
from xoot.models.fields import Id


class Event(NewEvent):
    """
    One append-only audit record of a mutation, as stored.

    before/after hold only the fields that changed (a full snapshot for a
    create). For items and decisions they include the version, which is
    how version conflicts are explained.
    """

    id: Id
