"""Partial item updates distinguish "unchanged" from "cleared"."""

import pytest
from pydantic import ValidationError

from xoot.models.item.item_update import ItemUpdate


def test_provided_returns_only_set_fields() -> None:
    """Unset fields are left out; an explicit None on a reference is kept."""
    update = ItemUpdate(title="new", backlog_session_id=None)
    assert update.provided() == {"backlog_session_id": None, "title": "new"}


@pytest.mark.parametrize("field", ["title", "body", "state"])
def test_required_fields_cannot_be_cleared(field: str) -> None:
    """title, body and state reject an explicit None."""
    with pytest.raises(ValidationError, match="cannot be cleared"):
        ItemUpdate.model_validate({field: None})
