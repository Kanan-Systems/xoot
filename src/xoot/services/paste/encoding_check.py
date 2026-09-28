"""
Spotting titles and bodies a clipboard code page may have damaged.

A console code page that cannot carry a character often writes "?" in its
place, and that is valid UTF-8, so decode_paste cannot refuse it. A "?"
directly between two letters of any script ("verificaci?n") is rare in real
text and typical of a lost accent, while "Why?", "?x" and "x ? y" are not.
The check only warns: it reads nothing but the block and never refuses it.
"""

from pydantic import BaseModel

from xoot.services.paste.models.fields import REF_PREFIX
from xoot.services.paste.models.paste_block import PasteBlock, PasteOp
from xoot.services.paste.models.paste_encoding_warning import PasteEncodingWarning

NO_TARGET = "-"
_TEXT_FIELDS = ("title", "body")
_LOST = "?"


def encoding_warnings(block: PasteBlock) -> tuple[PasteEncodingWarning, ...]:
    """
    Find every title and body in a block with a "?" between two letters.

    Update ops carry their title and body inside changes, so that is where
    they are read from.

    Args:
        - block (PasteBlock): the parsed block.

    Returns:
        - warnings (tuple[PasteEncodingWarning, ...]): one per damaged field,
          in op order; empty when nothing looks damaged.
    """
    warnings: list[PasteEncodingWarning] = []
    for index, op in enumerate(block.ops, 1):
        source: BaseModel = getattr(op, "changes", op)
        for field in _TEXT_FIELDS:
            text = getattr(source, field, None)
            if text and looks_damaged(text):
                warnings.append(
                    PasteEncodingWarning(index=index, target=_target(op), field=field)
                )
    return tuple(warnings)


def looks_damaged(text: str) -> bool:
    """
    Tell whether a "?" sits directly between two letters of any script.

    Args:
        - text (str): a title or body.

    Returns:
        - damaged (bool): at least one such "?" was found.
    """
    return any(
        char == _LOST and text[at - 1].isalpha() and text[at + 1].isalpha()
        for at, char in enumerate(text[1:-1], 1)
    )


def _target(op: PasteOp) -> str:
    """The key an op targets, else the $ref it defines, else NO_TARGET."""
    key: str | None = getattr(op, "key", None)
    if key:
        return key
    ref: str | None = getattr(op, "ref", None)
    return f"{REF_PREFIX}{ref}" if ref else NO_TARGET
