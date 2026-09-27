"""
The session and decision ops of a block: session_start, decision_record,
decision_update and session_close.

session_close plans the close first, in the same transaction, so missing or
unexpected dispositions are reported by key, and every stale session-backlog
item the close retires is listed as an auto-backlog side effect.
"""

from xoot.exceptions.disposition_error import DispositionError
from xoot.exceptions.paste_op_error import PasteOpError
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.decision.decision_update import DecisionUpdate
from xoot.models.session.session_close import SessionClose
from xoot.models.session.session_close_plan import SessionClosePlan
from xoot.models.session.session_start import SessionStart
from xoot.services.decision_service import create_decision_in, update_decision_in
from xoot.services.lookups import require_decision, require_item
from xoot.services.paste.changes import describe_changes, session_key_of
from xoot.services.paste.models.decision_record_op import DecisionRecordOp
from xoot.services.paste.models.decision_update_op import DecisionUpdateOp
from xoot.services.paste.models.paste_auto_backlog import PasteAutoBacklog
from xoot.services.paste.models.paste_change import PasteChange
from xoot.services.paste.models.paste_op_outcome import PasteOpOutcome
from xoot.services.paste.models.session_close_op import SessionCloseOp
from xoot.services.paste.models.session_start_op import SessionStartOp
from xoot.services.paste.paste_run import PasteRun
from xoot.services.session_close_service import close_session_in, plan_close_in
from xoot.services.session_service import start_session_in
from xoot.services.write_scope import changed_fields


def run_session_start(run: PasteRun, index: int, op: SessionStartOp) -> PasteOpOutcome:
    """
    Start the block's session, with client paste, and link its focus items.

    Args:
        - run (PasteRun): the block's run.
        - index (int): the op's 1-based position.
        - op (SessionStartOp): the op.

    Returns:
        - outcome (PasteOpOutcome): the new session's key.
    """
    focus = tuple(run.item(value).id for value in op.focus)
    request = SessionStart(title=op.title, focus_item_ids=focus)
    started = start_session_in(run.scope, run.project.id, request)
    run.attach(started.session)
    key = run.session_key(started.session)
    return PasteOpOutcome(index=index, op=op.op, key=key, created=True)


def run_decision_record(
    run: PasteRun, index: int, op: DecisionRecordOp
) -> PasteOpOutcome:
    """
    Record a decision, superseding an older one if asked.

    Args:
        - run (PasteRun): the block's run.
        - index (int): the op's 1-based position.
        - op (DecisionRecordOp): the op.

    Returns:
        - outcome (PasteOpOutcome): the new decision's key and ref, and the
          superseded decision's status change.
    """
    target = None if op.supersedes is None else run.decision(op.supersedes)
    request = DecisionCreate(
        title=op.title,
        body=op.body,
        status=DecisionStatus(op.status),
        supersedes_id=None if target is None else target.id,
        scope_item_id=None if op.scope is None else run.item(op.scope).id,
    )
    decision = create_decision_in(run.scope, run.project.id, request)
    outcome = run.created(index, op.op, decision, op.ref)
    if target is None:
        return outcome
    after = require_decision(run.conn, target.id)
    run.touch(after)
    diff = describe_changes(run.conn, target.key, *changed_fields(target, after))
    return outcome.model_copy(update={"changes": diff})


def run_decision_update(
    run: PasteRun, index: int, op: DecisionUpdateOp
) -> PasteOpOutcome:
    """
    Change a decision's title, body or status.

    Args:
        - run (PasteRun): the block's run.
        - index (int): the op's 1-based position.
        - op (DecisionUpdateOp): the op.

    Returns:
        - outcome (PasteOpOutcome): the fields changed.
    """
    decision = run.decision(op.key)
    version = decision.version if op.expected_version is None else op.expected_version
    request = DecisionUpdate(**op.changes.model_dump(exclude_unset=True))
    stored = update_decision_in(run.scope, decision.id, version, request)
    run.touch(stored)
    diff = describe_changes(run.conn, decision.key, *changed_fields(decision, stored))
    return PasteOpOutcome(index=index, op=op.op, key=decision.key, changes=diff)


def run_session_close(run: PasteRun, index: int, op: SessionCloseOp) -> PasteOpOutcome:
    """
    Close the block's session, applying every disposition.

    Args:
        - run (PasteRun): the block's run.
        - index (int): the op's 1-based position.
        - op (SessionCloseOp): the op.

    Returns:
        - outcome (PasteOpOutcome): the session's key, every disposition
          and the changes they make; auto-backlog moves go on the run.

    Raises:
        - PasteOpError: an item has two dispositions, a disposition names an
          item that needs none, or one is missing; keys are listed.
    """
    session = run.open_session()
    disposed = [(run.item(key), value) for key, value in op.dispositions.items()]
    by_id = {item.id: value for item, value in disposed}
    if len(by_id) != len(op.dispositions):
        raise PasteOpError(
            index, op.op, reason="an item is given more than one disposition"
        )
    request = SessionClose(summary=op.summary, dispositions=by_id)
    try:
        plan = plan_close_in(run.conn, session.id, request)
    except DispositionError as exc:
        keys = run.item_keys(exc.item_ids)
        reason = f"dispositions name items that need none: {keys}"
        raise PasteOpError(index, op.op, reason=reason) from exc
    if plan.missing_item_ids:
        missing = run.item_keys(plan.missing_item_ids)
        raise PasteOpError(index, op.op, reason=f"missing dispositions: {missing}")
    closed = close_session_in(run.scope, request)
    run.attach(closed)
    for item_id in sorted(by_id):
        run.touch(require_item(run.conn, item_id))
    return PasteOpOutcome(
        index=index,
        op=op.op,
        key=run.session_key(closed),
        changes=_close_changes(run, plan),
        dispositions={item.key: value for item, value in disposed},
    )


def _close_changes(run: PasteRun, plan: SessionClosePlan) -> tuple[PasteChange, ...]:
    """The disposition changes; each auto-backlog move is noted on the run."""
    entries: list[PasteChange] = []
    for change in plan.changes:
        entries.extend(
            describe_changes(run.conn, change.key, change.before, change.after)
        )
    for change in plan.auto_backlog:
        run.touch(require_item(run.conn, change.item_id))
        origin = session_key_of(run.conn, change.before.get("backlog_session_id"))
        run.auto_backlog.append(PasteAutoBacklog(key=change.key, origin_session=origin))
    return tuple(entries)
