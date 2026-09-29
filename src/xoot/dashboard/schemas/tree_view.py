"""What GET /api/v1/projects/{prefix}/tree returns."""

from pydantic import BaseModel, ConfigDict

from xoot.server.schemas.tree_entry import TreeEntry


class TreeView(BaseModel):
    """Tree nodes in pre-order; truncated says the bounds hid items."""

    model_config = ConfigDict(frozen=True)

    project: str
    nodes: list[TreeEntry]
    truncated: bool
