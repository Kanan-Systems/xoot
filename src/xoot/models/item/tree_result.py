"""The result of a bounded tree query."""

from pydantic import BaseModel, ConfigDict

from xoot.models.item.tree_node import TreeNode


class TreeResult(BaseModel):
    """
    Nodes in pre-order (each parent before its children). truncated is True
    when the depth or item limit hid items that would otherwise be shown.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    nodes: tuple[TreeNode, ...]
    truncated: bool
