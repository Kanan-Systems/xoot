"""The decision ops of a block: decision_record and decision_update."""

from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.decision.decision_status import DecisionStatus
from xoot.models.decision.decision_update import DecisionUpdate
from xoot.services.decision_service import create_decision_in, update_decision_in
from xoot.services.lookups import require_decision
from xoot.services.paste.changes import describe_changes
from xoot.services.paste.models.decision_record_op import DecisionRecordOp
from xoot.services.paste.models.decision_update_op import DecisionUpdateOp
from xoot.services.paste.models.paste_op_outcome import PasteOpOutcome
from xoot.services.paste.paste_run import PasteRun
from xoot.services.write_scope import changed_fields


def run_decision_record(
    run: PasteRun, index: int, op: DecisionRecordOp
) -> PasteOpOutcome:
    """
    Record a decision on its owner, superseding an older one if asked.

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
        owner_item_id=run.item(op.owner).id,
        title=op.title,
        body=op.body,
        status=DecisionStatus(op.status),
        supersedes_id=None if target is None else target.id,
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
