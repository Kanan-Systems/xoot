"""The decision_update op: change one decision."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from xoot.models.decision.decision_changes_input import DecisionChangesInput
from xoot.models.fields import Id
from xoot.services.paste.models.fields import DecisionKeyOrRef


class DecisionUpdateOp(BaseModel):
    """
    Changes one decision with the decision_update tool's changes model.
    expected_version follows the item_update rule.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    op: Literal["decision_update"]
    key: DecisionKeyOrRef
    expected_version: Id | None = None
    changes: DecisionChangesInput
