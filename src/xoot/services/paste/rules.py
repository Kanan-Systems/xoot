"""
The block rules that need no database: refs and versions.

Every key is checked against the key grammar of its kind (item or
decision), including the parent and awaited decision inside an
item_update's changes. A ref is defined once, by a capture, item_create, backlog_cover (naming the
new subtask) or decision_record, and "$<ref>" may only appear in a later op,
in a field of the matching kind. An update of a ref'd record omits
expected_version (the block created it); one of an existing record must
give it.
"""

from collections.abc import Iterator
from typing import Literal

from xoot.exceptions.paste_op_error import PasteOpError
from xoot.services.paste.models.backlog_cover_op import BacklogCoverOp
from xoot.services.paste.models.backlog_push_op import BacklogPushOp
from xoot.services.paste.models.capture_op import CaptureOp
from xoot.services.paste.models.decision_record_op import DecisionRecordOp
from xoot.services.paste.models.decision_update_op import DecisionUpdateOp
from xoot.services.paste.models.fields import is_ref, ref_name
from xoot.services.paste.models.item_create_op import ItemCreateOp
from xoot.services.paste.models.item_update_op import ItemUpdateOp
from xoot.services.paste.models.paste_block import PasteBlock, PasteOp
from xoot.utils.keys import is_decision_key, is_item_key

type RefKind = Literal["item", "decision"]

_ARTICLES: dict[RefKind, str] = {"item": "an item", "decision": "a decision"}


def check_block(block: PasteBlock) -> None:
    """
    Enforce the ref and version rules.

    Args:
        - block (PasteBlock): the parsed block.

    Raises:
        - PasteOpError: an op breaks a ref or version rule; the message
          names the op.
    """
    defined: dict[str, RefKind] = {}
    for index, op in enumerate(block.ops, start=1):
        for value, kind in _uses(op):
            _check_use(index, op.op, value, kind, defined)
        _check_version(index, op)
        _define(index, op, defined)


def _uses(op: PasteOp) -> Iterator[tuple[str, RefKind]]:
    """Every key field of an op with the kind of record it must name."""
    if isinstance(op, ItemCreateOp):
        yield from _present(op.parent, "item")
    elif isinstance(op, ItemUpdateOp):
        yield op.key, "item"
        yield from _present(op.changes.parent, "item")
        yield from _present(op.changes.awaiting_decision, "decision")
    elif isinstance(op, CaptureOp):
        yield op.found_on, "item"
    elif isinstance(op, BacklogCoverOp):
        yield op.key, "item"
        yield from _present(op.batch, "item")
    elif isinstance(op, BacklogPushOp):
        yield op.key, "item"
    elif isinstance(op, DecisionRecordOp):
        yield op.owner, "item"
        yield from _present(op.supersedes, "decision")
    elif isinstance(op, DecisionUpdateOp):
        yield op.key, "decision"


def _present(value: str | None, kind: RefKind) -> Iterator[tuple[str, RefKind]]:
    if value is not None:
        yield value, kind


def _check_use(
    index: int, op: str, value: str, kind: RefKind, defined: dict[str, RefKind]
) -> None:
    """
    A key must fit the grammar of its kind; a $ref must be well formed,
    defined by an earlier op, and of this kind. Neither is ever echoed.
    """
    if not is_ref(value):
        valid = is_item_key(value) if kind == "item" else is_decision_key(value)
        if not valid:
            raise PasteOpError(index, op, reason=f"not {_ARTICLES[kind]} key or $ref")
        return
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
    if not isinstance(op, (CaptureOp, ItemCreateOp, BacklogCoverOp, DecisionRecordOp)):
        return
    if op.ref is None:
        return
    if op.ref in defined:
        raise PasteOpError(index, op.op, reason=f"duplicate ref ${op.ref}")
    defined[op.ref] = "decision" if isinstance(op, DecisionRecordOp) else "item"
