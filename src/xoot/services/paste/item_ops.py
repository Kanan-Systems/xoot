"""
The item ops of a block: item_create, item_update, capture, backlog_cover
and backlog_push.

item_update chooses its path with the item_update tool's own rules: a parent
change or a drop of an item with children must come alone. Unlike the tools,
a subtree drop, reparent or push needs no confirm token here: the dry-run
plan the user confirms takes its place.
"""

from xoot.models.item.item_changes_input import ItemChangesInput
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.item.subtree_plan import SubtreePlan
from xoot.services.backlog_push_service import apply_push_in
from xoot.services.backlog_service import capture_in, cover_in
from xoot.services.item_service import create_item_in, update_item_in
from xoot.services.lookups import require_item
from xoot.services.paste.changes import describe_changes
from xoot.services.paste.models.backlog_cover_op import BacklogCoverOp
from xoot.services.paste.models.backlog_push_op import BacklogPushOp
from xoot.services.paste.models.capture_op import CaptureOp
from xoot.services.paste.models.item_create_op import ItemCreateOp
from xoot.services.paste.models.item_update_op import ItemUpdateOp
from xoot.services.paste.models.paste_change import PasteChange
from xoot.services.paste.models.paste_op_outcome import PasteOpOutcome
from xoot.services.paste.paste_run import PasteRun
from xoot.services.subtree_service import apply_drop_in, apply_reparent_in
from xoot.services.update_paths import choose_path, item_update_from
from xoot.services.write_scope import changed_fields


def run_item_create(run: PasteRun, index: int, op: ItemCreateOp) -> PasteOpOutcome:
    """
    Create a goal, batch or subtask in the block's project.

    Args:
        - run (PasteRun): the block's run.
        - index (int): the op's 1-based position.
        - op (ItemCreateOp): the op.

    Returns:
        - outcome (PasteOpOutcome): the new item's key and ref.
    """
    parent_id = None if op.parent is None else run.item(op.parent).id
    request = ItemCreate(
        kind=ItemKind(op.kind), title=op.title, body=op.body, parent_id=parent_id
    )
    item = create_item_in(run.scope, run.project.id, request)
    return run.created(index, op.op, item, op.ref)


def run_capture(run: PasteRun, index: int, op: CaptureOp) -> PasteOpOutcome:
    """
    Capture a backlog item next to the item it was found on.

    Args:
        - run (PasteRun): the block's run.
        - index (int): the op's 1-based position.
        - op (CaptureOp): the op.

    Returns:
        - outcome (PasteOpOutcome): the new item's key and ref.
    """
    found_on = run.item(op.found_on)
    draft = ItemDraft(title=op.title, body=op.body)
    item = capture_in(run.scope, run.project.id, found_on.id, draft)
    return run.created(index, op.op, item, op.ref)


def run_backlog_cover(run: PasteRun, index: int, op: BacklogCoverOp) -> PasteOpOutcome:
    """
    Cover a backlog item with a new subtask and close it.

    Args:
        - run (PasteRun): the block's run.
        - index (int): the op's 1-based position.
        - op (BacklogCoverOp): the op.

    Returns:
        - outcome (PasteOpOutcome): the new subtask's key and ref, and the
          closed item's state change.
    """
    backlog = run.item(op.key)
    batch_id = None if op.batch is None else run.item(op.batch).id
    subtask, closed = cover_in(run.scope, backlog.id, batch_id)
    run.touch(closed)
    outcome = run.created(index, op.op, subtask, op.ref)
    diff = describe_changes(run.conn, backlog.key, *changed_fields(backlog, closed))
    return outcome.model_copy(update={"changes": diff})


def run_backlog_push(run: PasteRun, index: int, op: BacklogPushOp) -> PasteOpOutcome:
    """
    Push a backlog item one level up.

    Args:
        - run (PasteRun): the block's run.
        - index (int): the op's 1-based position.
        - op (BacklogPushOp): the op.

    Returns:
        - outcome (PasteOpOutcome): the item's old key and its key change.
    """
    item = run.item(op.key)
    plan = apply_push_in(run.scope, item.id, None)
    return PasteOpOutcome(
        index=index, op=op.op, key=item.key, changes=_plan_changes(run, plan)
    )


def run_item_update(run: PasteRun, index: int, op: ItemUpdateOp) -> PasteOpOutcome:
    """
    Change an item directly, or drop or reparent it with its subtree.

    Args:
        - run (PasteRun): the block's run.
        - index (int): the op's 1-based position.
        - op (ItemUpdateOp): the op.

    Returns:
        - outcome (PasteOpOutcome): every field changed; a reparent lists
          each re-keyed descendant.
    """
    item = run.item(op.key)
    # A ref'd item was created in this block, at the version it has now.
    version = item.version if op.expected_version is None else op.expected_version
    changes = op.changes
    path, _ = choose_path(run.conn, item, changes.model_fields_set, changes.state)
    if path == "update":
        updated = update_item_in(run.scope, item.id, version, _request(run, changes))
        run.touch(updated)
        diff = describe_changes(run.conn, item.key, *changed_fields(item, updated))
        return PasteOpOutcome(index=index, op=op.op, key=item.key, changes=diff)
    plan: SubtreePlan
    if path == "reparent":
        parent = None if changes.parent is None else run.item(changes.parent).id
        plan = apply_reparent_in(run.scope, item.id, parent, version)
    else:
        plan = apply_drop_in(run.scope, item.id, version, state=changes.state)
    return PasteOpOutcome(
        index=index, op=op.op, key=item.key, changes=_plan_changes(run, plan)
    )


def _plan_changes(run: PasteRun, plan: SubtreePlan) -> tuple[PasteChange, ...]:
    """Touch every written row and describe its change."""
    entries: list[PasteChange] = []
    for change in plan.changes:
        run.touch(require_item(run.conn, change.item_id))
        entries.extend(
            describe_changes(run.conn, change.key, change.before, change.after)
        )
    return tuple(entries)


def _request(run: PasteRun, changes: ItemChangesInput) -> ItemUpdate:
    """Translate the key-based changes, refs included, into the id-based update."""
    return item_update_from(changes, lambda key: run.decision(key).id)
