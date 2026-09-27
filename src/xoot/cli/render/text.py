"""
Terminal-safe text: escaping stored strings and laying out tables.

Titles, names and paths are authored data. A control character (an ANSI
escape, a carriage return) or a bidirectional override could rewrite what
the terminal shows, so each is shown as a visible \\u escape instead.
"""

import unicodedata
from collections.abc import Sequence

# Cc: control characters; Cf: format characters such as bidi overrides;
# Zl/Zp: line and paragraph separators, which break a line like "\n" does.
_UNSAFE = frozenset({"Cc", "Cf", "Zl", "Zp"})


def clean(text: str) -> str:
    """
    Escape every character that could control the terminal.

    Args:
        - text (str): stored or caller-supplied text.

    Returns:
        - text (str): the same text with unsafe characters as \\uXXXX.
    """
    return "".join(
        f"\\u{ord(char):04x}" if unicodedata.category(char) in _UNSAFE else char
        for char in text
    )


def table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """
    Lay out rows under headers in left-aligned columns.

    Args:
        - headers (Sequence[str]): the column titles.
        - rows (Sequence[Sequence[str]]): the cells, already cleaned.

    Returns:
        - text (str): the table, one line per row, no trailing spaces.
    """
    widths = [
        max(len(cells[i]) for cells in (headers, *rows)) for i in range(len(headers))
    ]
    lines = [
        "  ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()
        for cells in (headers, *rows)
    ]
    return "\n".join(lines)
