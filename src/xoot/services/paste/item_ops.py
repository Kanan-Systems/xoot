"""
The item ops of a block: capture, item_create and item_update.

item_update chooses its path with the item_update tool's own rules: a parent
change or a drop of an item with children must come alone. Unlike the tool,
a subtree drop or reparent needs no confirm token here: the dry-run plan the
user confirms takes its place.
"""

from xoot.models.item.item_changes_input import ItemChangesInput
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_update import ItemUpdate
from xoot.models.item.subtree_plan import SubtreePlan
from xoot.services import key_resolver
from xoot.services.item_service import capture_in, create_item_in, update_item_in
from xoot.services.lookups import require_item
from xoot.services.paste.changes import describe_changes
from xoot.services.paste.models.capture_op import CaptureOp
from xoot.services.paste.models.item_create_op import ItemCreateOp
from xoot.services.paste.models.item_update_op import ItemUpdateOp
from xoot.services.paste.models.paste_change import PasteChange
from xoot.services.paste.models.paste_op_outcome import PasteOpOutcome
from xoot.services.paste.paste_run import PasteRun
from xoot.services.subtree_service import apply_drop_in, apply_reparent_in
from xoot.services.update_paths import choose_path, item_update_from
from xoot.services.write_scope import changed_fields


def run_capture(run: PasteRun, index: int, op: CaptureOp) -> PasteOpOutcome:
    """
    Park an unfiled subtask in the session's backlog.

    Args:
        - run (PasteRun): the block's run.
        - index (int): the op's 1-based position.
        - op (CaptureOp): the op.

    Returns:
        - outcome (PasteOpOutcome): the new item's key and ref.
    """
    item = capture_in(run.scope, ItemDraft(title=op.title, body=op.body))
    return run.created(index, op.op, item, op.ref)


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
        kind=op.kind, title=op.title, body=op.body, parent_id=parent_id
    )
    item = create_item_in(run.scope, run.project.id, request)
    return run.created(index, op.op, item, op.ref)


def run_item_update(run: PasteRun, index: int, op: ItemUpdateOp) -> PasteOpOutcome:
    """
    Change an item directly, or drop or reparent it with its subtree.

    Args:
        - run (PasteRun): the block's run.
        - index (int): the op's 1-based position.
        - op (ItemUpdateOp): the op.

    Returns:
        - outcome (PasteOpOutcome): every field changed, and for a reparent
          the descendants carried along.
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
    entries: list[PasteChange] = []
    for change in plan.changes:
        run.touch(require_item(run.conn, change.item_id))
        entries.extend(
            describe_changes(run.conn, change.key, change.before, change.after)
        )
    carried = (require_item(run.conn, i).key for i in plan.carried_item_ids)
    return PasteOpOutcome(
        index=index,
        op=op.op,
        key=item.key,
        changes=tuple(entries),
        carried=tuple(carried),
    )


def _request(run: PasteRun, changes: ItemChangesInput) -> ItemUpdate:
    """Translate the key-based changes, refs included, into the id-based update."""
    return item_update_from(
        changes,
        lambda key: key_resolver.session_by_key(run.conn, key).id,
        lambda key: run.decision(key).id,
    )
