"""
The changes argument of decision_update.

The model lives in models/ so services (paste mode) can use it without
importing the server; it is re-exported here for the tool schemas.
"""

from xoot.models.decision.decision_changes_input import DecisionChangesInput

__all__ = ["DecisionChangesInput"]
