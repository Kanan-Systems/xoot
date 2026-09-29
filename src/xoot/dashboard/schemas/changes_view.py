"""What GET /api/v1/projects/{prefix}/changes returns."""

from pydantic import BaseModel, ConfigDict


class ChangesView(BaseModel):
    """The project's newest event id; the dashboard polls it for changes."""

    model_config = ConfigDict(frozen=True)

    latest_event_id: int
