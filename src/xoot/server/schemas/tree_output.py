"""What tree_get returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.literals import ResolvedBy
from xoot.server.schemas.tree_entry import TreeEntry


class TreeOutput(BaseModel):
    """Nodes in pre-order; truncated when depth or limit hid items."""

    model_config = ConfigDict(frozen=True)

    project: str
    resolved_by: ResolvedBy
    nodes: list[TreeEntry]
    truncated: bool
