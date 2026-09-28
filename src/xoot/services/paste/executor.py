"""
Dry-running and applying a checked block.

The dry run executes the whole block in a write transaction and always rolls
it back, so nothing persists: no rows, events, counters or sqlite_sequence
entries. The apply executes it again in a fresh transaction and compares the
canonical digest of its result with the dry run's before committing; any
difference (another writer got in between) rolls back and refuses.
"""

import sqlite3
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from xoot.exceptions.paste_error import PasteError
from xoot.exceptions.paste_op_error import PasteOpError
from xoot.exceptions.xoot_error import XootError
from xoot.services.paste.item_ops import run_capture, run_item_create, run_item_update
from xoot.services.paste.models.capture_op import CaptureOp
from xoot.services.paste.models.decision_record_op import DecisionRecordOp
from xoot.services.paste.models.decision_update_op import DecisionUpdateOp
from xoot.services.paste.models.item_create_op import ItemCreateOp
from xoot.services.paste.models.item_update_op import ItemUpdateOp
from xoot.services.paste.models.paste_block import PasteBlock, PasteOp
from xoot.services.paste.models.paste_op_outcome import PasteOpOutcome
from xoot.services.paste.models.paste_result import PasteResult
from xoot.services.paste.models.session_close_op import SessionCloseOp
from xoot.services.paste.models.session_start_op import SessionStartOp
from xoot.services.paste.paste_run import PasteRun
from xoot.services.paste.record_ops import (
    run_decision_record,
    run_decision_update,
    run_session_close,
    run_session_start,
)
from xoot.store.store import Store
from xoot.utils.utils import canonical_sha256

PLAN_CHANGED = "plan changed since preview; run paste apply again"

_HANDLERS: dict[type, Callable[[PasteRun, int, Any], PasteOpOutcome]] = {
    SessionStartOp: run_session_start,
    CaptureOp: run_capture,
    ItemCreateOp: run_item_create,
    ItemUpdateOp: run_item_update,
    DecisionRecordOp: run_decision_record,
    DecisionUpdateOp: run_decision_update,
    SessionCloseOp: run_session_close,
}


class _DryRunDone(Exception):
    """Unwinds the dry run's transaction, carrying the result out of it."""

    def __init__(self, result: PasteResult) -> None:
        super().__init__("dry run complete")
        self.result = result


def dry_run(store: Store, block: PasteBlock) -> PasteResult:
    """
    Execute a block and roll everything back.

    Args:
        - store (Store): the database.
        - block (PasteBlock): the checked block.

    Returns:
        - result (PasteResult): what the block would do.

    Raises:
        - PasteError: the project or session cannot be used.
        - PasteOpError: an op failed; the message names it.
    """
    try:
        with store.write() as conn:
            raise _DryRunDone(_execute(conn, block))
    except _DryRunDone as done:
        return done.result


def apply(store: Store, block: PasteBlock, expected_digest: str) -> PasteResult:
    """
    Execute a block and commit it, only if it does what the dry run showed.

    Args:
        - store (Store): the database.
        - block (PasteBlock): the same checked block the dry run ran.
        - expected_digest (str): result_digest of the dry run's result.

    Returns:
        - result (PasteResult): what the block did.

    Raises:
        - PasteError: the result differs from the dry run's, or the project
          or session cannot be used.
        - PasteOpError: an op failed; the message names it.
    """
    with store.write() as conn:
        result = _execute(conn, block)
        if result_digest(result) != expected_digest:
            raise PasteError(PLAN_CHANGED)
    return result


def result_digest(result: PasteResult) -> str:
    """
    Digest a result canonically, leaving out its encoding warnings.

    Args:
        - result (PasteResult): a dry run's or an apply's result.

    Returns:
        - digest (str): lowercase hex SHA-256.
    """
    return canonical_sha256(result.model_dump(mode="json", exclude={"warnings"}))


def _execute(conn: sqlite3.Connection, block: PasteBlock) -> PasteResult:
    """Run every op in order; the first failure refuses the whole block."""
    run = PasteRun(conn, block)
    outcomes = [_run_op(run, index, op) for index, op in enumerate(block.ops, 1)]
    return run.result(outcomes)


def _run_op(run: PasteRun, index: int, op: PasteOp) -> PasteOpOutcome:
    try:
        return _HANDLERS[type(op)](run, index, op)
    except PasteOpError:
        raise
    except (XootError, ValidationError) as exc:
        raise PasteOpError(index, op.op, cause=exc) from exc
