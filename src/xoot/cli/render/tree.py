"""The text form of `xoot tree`: one indented line per item."""

from xoot.cli.render.text import clean
from xoot.server.schemas.tree_output import TreeOutput

INDENT = "  "


def render_tree(output: TreeOutput) -> str:
    """
    Render tree nodes in pre-order, indented by depth.

    Each line shows the key, kind, state, category and title; unfiled
    subtasks are marked.

    Args:
        - output (TreeOutput): the tree.

    Returns:
        - text (str): the lines, or "(no items)".
    """
    lines = []
    for node in output.nodes:
        item = node.item
        category = item.category or "unknown"
        unfiled = " [unfiled]" if node.unfiled else ""
        lines.append(
            f"{INDENT * node.depth}{item.key}  {item.kind}  {item.state} "
            f"({category})  {clean(item.title)}{unfiled}"
        )
    return "\n".join(lines) or "(no items)"
