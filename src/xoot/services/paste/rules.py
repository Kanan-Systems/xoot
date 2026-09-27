"""
The block rules that need no database: session, op order, refs and versions.

A block names an open session or starts one with its first op, never both
and never neither. session_start may only come first and session_close only
last. A ref is defined once, by an item_create or decision_record, and
"$<ref>" may only appear in a later op, in a field of the matching kind; the
session is implied and never referenced by $. An update of a ref'd record
omits expected_version (the block created it); one of an existing record
must give it.
"""

from collections.abc import Iterator
from typing import Literal

from xoot.exceptions.paste_error import PasteError
from xoot.exceptions.paste_op_error import PasteOpError
from xoot.services.paste.models.decision_record_op import DecisionRecordOp
from xoot.services.paste.models.decision_update_op import DecisionUpdateOp
from xoot.services.paste.models.fields import is_ref, ref_name
from xoot.services.paste.models.item_create_op import ItemCreateOp
from xoot.services.paste.models.item_update_op import ItemUpdateOp
from xoot.services.paste.models.paste_block import PasteBlock, PasteOp
from xoot.services.paste.models.session_close_op import SessionCloseOp
from xoot.services.paste.models.session_start_op import SessionStartOp

type RefKind = Literal["item", "decision", "session"]

BOTH_SESSIONS = 'give either "session" or a first session_start op, not both'
_ARTICLES: dict[RefKind, str] = {
    "item": "an item",
    "decision": "a decision",
    "session": "a session",
}
NO_SESSION = (
    'a session is required: name an open one in "session" or start one '
    "with a first session_start op"
)


def check_block(block: PasteBlock) -> None:
    """
    Enforce the session, op order, ref and version rules.

    Args:
        - block (PasteBlock): the parsed block.

    Raises:
        - PasteError: the session is named twice or not at all.
        - PasteOpError: an op is out of place, or breaks a ref or version
          rule; the message names the op.
    """
    starts = isinstance(block.ops[0], SessionStartOp)
    if block.session is not None and starts:
        raise PasteError(BOTH_SESSIONS)
    if block.session is None and not starts:
        raise PasteError(NO_SESSION)
    last = len(block.ops)
    defined: dict[str, RefKind] = {}
    for index, op in enumerate(block.ops, start=1):
        if isinstance(op, SessionStartOp) and index != 1:
            raise PasteOpError(
                index, op.op, reason="session_start must be the first op"
            )
        if isinstance(op, SessionCloseOp) and index != last:
            raise PasteOpError(index, op.op, reason="session_close must be the last op")
        for value, kind in _uses(op):
            _check_use(index, op.op, value, kind, defined)
        _check_version(index, op)
        _define(index, op, defined)


def _uses(op: PasteOp) -> Iterator[tuple[str, RefKind]]:
    """Every key field of an op with the kind of record it must name."""
    if isinstance(op, SessionStartOp):
        yield from ((key, "item") for key in op.focus)
    elif isinstance(op, ItemCreateOp):
        yield from _present(op.parent, "item")
    elif isinstance(op, ItemUpdateOp):
        yield op.key, "item"
        yield from _present(op.changes.parent, "item")
        yield from _present(op.changes.awaiting_decision, "decision")
        yield from _present(op.changes.backlog_session, "session")
    elif isinstance(op, DecisionRecordOp):
        yield from _present(op.scope, "item")
        yield from _present(op.supersedes, "decision")
    elif isinstance(op, DecisionUpdateOp):
        yield op.key, "decision"
    elif isinstance(op, SessionCloseOp):
        yield from ((key, "item") for key in op.dispositions)


def _present(value: str | None, kind: RefKind) -> Iterator[tuple[str, RefKind]]:
    if value is not None:
        yield value, kind


def _check_use(
    index: int, op: str, value: str, kind: RefKind, defined: dict[str, RefKind]
) -> None:
    """A $ref must be well formed, defined by an earlier op, and of this kind."""
    if not is_ref(value):
        return
    if kind == "session":
        raise PasteOpError(
            index, op, reason="a session is never referenced by $; use its key"
        )
    name = ref_name(value)
    if name is None:
        raise PasteOpError(index, op, reason="malformed ref")
    if name not in defined:
        raise PasteOpError(index, op, reason=f"${name} is not defined by an earlier op")
    if defined[name] != kind:
        raise PasteOpError(
            index,
            op,
            reason=f"${name} names {_ARTICLES[defined[name]]}; {_ARTICLES[kind]} "
            "is expected here",
        )


def _check_version(index: int, op: PasteOp) -> None:
    """A ref'd record was created here, so its version is not the caller's to give."""
    if not isinstance(op, (ItemUpdateOp, DecisionUpdateOp)):
        return
    record = "item" if isinstance(op, ItemUpdateOp) else "decision"
    if is_ref(op.key) and op.expected_version is not None:
        raise PasteOpError(
            index,
            op.op,
            reason=f"omit expected_version for a {record} created in this block",
        )
    if not is_ref(op.key) and op.expected_version is None:
        raise PasteOpError(
            index,
            op.op,
            reason=f"expected_version is required for an existing {record}",
        )


def _define(index: int, op: PasteOp, defined: dict[str, RefKind]) -> None:
    if not isinstance(op, (ItemCreateOp, DecisionRecordOp)) or op.ref is None:
        return
    if op.ref in defined:
        raise PasteOpError(index, op.op, reason=f"duplicate ref ${op.ref}")
    defined[op.ref] = "item" if isinstance(op, ItemCreateOp) else "decision"
