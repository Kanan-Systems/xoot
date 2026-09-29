"""The text form of `xoot tree`: one indented line per item."""

from xoot.cli.render.text import clean
from xoot.server.schemas.tree_output import TreeOutput

INDENT = "  "


def render_tree(output: TreeOutput) -> str:
    """
    Render tree nodes in pre-order, indented by depth.

    Each line shows the key, kind, state, category and title. The indented
    key, the kind and the state with its category are padded to columns, so
    every title starts at one offset.

    Args:
        - output (TreeOutput): the tree.

    Returns:
        - text (str): the lines, or "(no items)".
    """
    if not output.nodes:
        return "(no items)"
    columns = [
        (
            f"{INDENT * node.depth}{node.item.key}",
            f"{node.item.kind}",
            f"{node.item.state} ({node.item.category or 'unknown'})",
        )
        for node in output.nodes
    ]
    widths = [max(len(cells[i]) for cells in columns) for i in range(3)]
    lines = []
    for node, cells in zip(output.nodes, columns):
        padded = "  ".join(cell.ljust(width) for cell, width in zip(cells, widths))
        lines.append(f"{padded}  {clean(node.item.title)}")
    return "\n".join(lines)
