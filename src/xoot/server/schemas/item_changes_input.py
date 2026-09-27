"""
The changes argument of item_update.

The model lives in models/ so services (paste mode) can use it without
importing the server; it is re-exported here for the tool schemas.
"""

from xoot.models.item.item_changes_input import ItemChangesInput

__all__ = ["ItemChangesInput"]
