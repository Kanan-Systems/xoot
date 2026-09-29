"""
Executing a block: one transaction and one scope for the whole block. The
dry run persists nothing; any op failure refuses the whole block; the apply
commits only when its result digests the same as the dry run's. Writes are
Claude's through client paste, and the result carries what the completion
engine did.
"""

from collections.abc import Callable
from typing import Any

import pytest

from xoot.cli.render.errors import error_message
from xoot.exceptions.paste_error import PasteError
from xoot.exceptions.paste_op_error import PasteOpError
from xoot.exceptions.update_path_error import UpdatePathError
from xoot.exceptions.version_conflict_error import VersionConflictError
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client
from xoot.models.event.write_context import WriteContext
from xoot.models.item.blocked_item import BlockedItem
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.repositories.event import event_db
from xoot.services.item_service import get_item, update_item
from xoot.services.paste.executor import (
    PLAN_CHANGED,
    apply,
    dry_run,
    result_digest,
)
from xoot.services.paste.models.paste_result import PasteResult
from xoot.services.paste.parser import parse_paste
from xoot.store.store import Store

type Tree = tuple[Item, Item, Item, Item]

FULL_BLOCK = [
    {"op": "item_create", "ref": "g", "kind": "goal", "title": "goal"},
    {"op": "item_create", "ref": "b", "kind": "batch", "title": "b", "parent": "$g"},
    {"op": "item_create", "ref": "t", "kind": "subtask", "title": "t", "parent": "$b"},
    {"op": "capture", "ref": "c", "found_on": "$t", "title": "side", "body": "why"},
    {"op": "item_update", "key": "$t", "changes": {"state": "active"}},
    {
        "op": "decision_record",
        "ref": "d",
        "owner": "$b",
        "title": "use sqlite",
        "body": "local only",
        "status": "locked",
    },
    {"op": "decision_update", "key": "$d", "changes": {"status": "deferred"}},
]


@pytest.mark.usefixtures("project")
def test_dry_run_persists_nothing(
    store: Store,
    fenced: Callable[..., str],
    snapshot: Callable[[], dict[str, Any]],
) -> None:
    """Rows, the dump, sqlite_sequence and the counters are all untouched."""
    before = snapshot()
    result = dry_run(store, parse_paste(fenced(FULL_BLOCK)))
    assert snapshot() == before
    assert result.project == "xoot"
    assert [o.key for o in result.outcomes] == [
        "goal-1",
        "goal-1/batch-1",
        "goal-1/batch-1/subtask-1",
        "goal-1/batch-1/backlog-1",
        "goal-1/batch-1/subtask-1",
        "goal-1/batch-1/decision-1",
        "goal-1/batch-1/decision-1",
    ]
    assert result.refs["d"] == "goal-1/batch-1/decision-1"


@pytest.mark.usefixtures("project")
def test_dry_run_matches_the_apply(
    store: Store, fenced: Callable[..., str], snapshot: Callable[[], dict[str, Any]]
) -> None:
    """Twice the same dry run, then an apply with the same result."""
    block = parse_paste(fenced(FULL_BLOCK))
    first, second = dry_run(store, block), dry_run(store, block)
    before = snapshot()
    applied = apply(store, block, result_digest(first))
    assert first == second == applied
    assert snapshot() != before


@pytest.mark.usefixtures("project")
def test_failure_at_op_3_of_5_writes_nothing(
    store: Store, fenced: Callable[..., str], snapshot: Callable[[], dict[str, Any]]
) -> None:
    """Ops 1-2 ran inside the transaction; op 3 fails; everything rolls back."""
    ops = [
        {"op": "item_create", "ref": "g", "kind": "goal", "title": "goal"},
        {"op": "capture", "found_on": "$g", "title": "c"},
        {"op": "item_update", "key": "$g", "changes": {"state": "no_such_state"}},
        {"op": "capture", "found_on": "$g", "title": "d"},
        {"op": "capture", "found_on": "$g", "title": "e"},
    ]
    before = snapshot()
    block = parse_paste(fenced(ops))
    with pytest.raises(PasteOpError) as caught:
        dry_run(store, block)
    assert (caught.value.index, caught.value.op) == (3, "item_update")
    assert error_message(caught.value).startswith(
        "error: PasteOpError: op 3 (item_update): StateError: "
    )
    with pytest.raises(PasteOpError, match=r"^op 3 \(item_update\)$"):
        apply(store, block, "0" * 64)
    assert snapshot() == before


def test_plan_changed_by_a_new_key_is_refused(
    store: Store,
    work_tree: Tree,
    capture_on: Callable[..., Item],
    fenced: Callable[..., str],
) -> None:
    """Another writer takes the next number: the previewed keys would be wrong."""
    _, batch, first, _ = work_tree
    block = parse_paste(
        fenced([{"op": "capture", "found_on": first.key, "title": "c"}])
    )
    preview = dry_run(store, block)
    capture_on(batch)
    with pytest.raises(PasteError, match=f"^{PLAN_CHANGED}$"):
        apply(store, block, result_digest(preview))


def test_plan_changed_by_an_out_of_band_write_is_refused(
    store: Store,
    ctx: WriteContext,
    work_tree: Tree,
    fenced: Callable[..., str],
    snapshot: Callable[[], dict[str, Any]],
) -> None:
    """
    The batch completed between preview and apply, so the capture would now
    reopen it: the result differs and nothing is written.
    """
    _, _, first, second = work_tree
    block = parse_paste(
        fenced([{"op": "capture", "found_on": first.key, "title": "c"}])
    )
    preview = dry_run(store, block)
    assert preview.reopened == ()
    update_item(store, first.id, 1, ItemUpdate(state="done"), ctx)
    update_item(store, second.id, 1, ItemUpdate(state="done"), ctx)
    before = snapshot()
    with pytest.raises(PasteError, match=f"^{PLAN_CHANGED}$"):
        apply(store, block, result_digest(preview))
    assert snapshot() == before


def test_version_conflict_carries_fields_and_actor(
    project: Project,
    store: Store,
    ctx: WriteContext,
    make_item: Callable[..., Item],
    fenced: Callable[..., str],
) -> None:
    """The user renamed the item since the chat read version 1."""
    item = make_item(project, ItemKind.GOAL)
    update_item(store, item.id, 1, ItemUpdate(title="renamed"), ctx)
    update = {
        "op": "item_update",
        "key": item.key,
        "expected_version": 1,
        "changes": {"state": "active"},
    }
    with pytest.raises(PasteOpError) as caught:
        dry_run(store, parse_paste(fenced([update])))
    assert isinstance(caught.value.cause, VersionConflictError)
    assert error_message(caught.value) == (
        "error: PasteOpError: op 1 (item_update): VersionConflictError: goal-1 "
        "is at version 2; changed since your version: title; by: user/cli"
    )


def test_events_are_claude_through_paste(
    project: Project,
    store: Store,
    fenced: Callable[..., str],
    paste: Callable[[str], PasteResult],
) -> None:
    """Every event of the block is actor claude, client paste, one timestamp."""
    with store.read() as conn:
        seen = len(event_db.list_for_project(conn, project.id))
    paste(fenced(FULL_BLOCK))
    with store.read() as conn:
        ours = event_db.list_for_project(conn, project.id)[seen:]
    assert ours and {(e.actor_kind, e.client) for e in ours} == {
        (ActorKind.CLAUDE, Client.PASTE)
    }
    assert len({e.created_at for e in ours}) == 1


def test_completion_is_reported(
    work_tree: Tree,
    capture_on: Callable[..., Item],
    fenced: Callable[..., str],
    paste: Callable[[str], PasteResult],
) -> None:
    """Blocked, then completed, then reopened: each block's result says so."""
    goal, batch, first, second = work_tree
    capture_on(first)
    done = [
        {"op": "item_update", "key": item.key, "expected_version": 1,
         "changes": {"state": "done"}}
        for item in (first, second)
    ]  # fmt: skip
    result = paste(fenced(done))
    assert result.blocked == (BlockedItem(key=batch.key, open_backlog=1),)
    resolve = {
        "op": "item_update",
        "key": "goal-1/batch-1/backlog-1",
        "expected_version": 1,
        "changes": {"state": "done"},
    }
    result = paste(fenced([resolve]))
    assert result.completed == (batch.key, goal.key)
    result = paste(fenced([{"op": "capture", "found_on": first.key, "title": "x"}]))
    assert result.reopened == (batch.key, goal.key)


def test_cover_and_push_run_without_tokens(
    work_tree: Tree,
    capture_on: Callable[..., Item],
    fenced: Callable[..., str],
    paste: Callable[[str], PasteResult],
) -> None:
    """The dry-run plan stands in for the tools' confirm tokens."""
    goal, batch, first, _ = work_tree
    capture_on(first)
    capture_on(first)
    ops = [
        {"op": "backlog_cover", "ref": "s", "key": "goal-1/batch-1/backlog-1"},
        {"op": "backlog_push", "key": "xoot:goal-1/batch-1/backlog-2"},
    ]
    result = paste(fenced(ops))
    assert result.refs == {"s": "goal-1/batch-1/subtask-3"}
    push = result.outcomes[1]
    assert [(c.field, c.before, c.after) for c in push.changes] == [
        ("key", "goal-1/batch-1/backlog-2", "goal-1/backlog-1"),
        ("parent", batch.key, goal.key),
    ]


# Each fixture the test needs is one argument.
def test_subtree_drop_and_reparent_need_no_token(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    project: Project,
    store: Store,
    work_tree: Tree,
    make_item: Callable[..., Item],
    fenced: Callable[..., str],
    paste: Callable[[str], PasteResult],
) -> None:
    """A reparent re-keys the subtree; a drop drops it; both apply at once."""
    _, batch, first, _ = work_tree
    target = make_item(project, ItemKind.GOAL)
    ops = [
        {"op": "item_update", "key": batch.key, "expected_version": 1,
         "changes": {"parent": target.key}},
    ]  # fmt: skip
    result = paste(fenced(ops))
    assert get_item(store, first.id).key == "goal-2/batch-1/subtask-1"
    assert "goal-2/batch-1/subtask-1" in {i.key for i in result.items}
    drop = [
        {"op": "item_update", "key": "goal-2/batch-1", "expected_version": 2,
         "changes": {"state": "dropped"}},
    ]  # fmt: skip
    paste(fenced(drop))
    assert get_item(store, first.id).state == "dropped"


def test_alone_rules_match_the_tool(
    store: Store, work_tree: Tree, fenced: Callable[..., str]
) -> None:
    """A parent change combined with another field is refused, as in the tool."""
    batch = work_tree[1]
    op = {
        "op": "item_update",
        "key": batch.key,
        "expected_version": 1,
        "changes": {"parent": "goal-1", "title": "x"},
    }
    with pytest.raises(PasteOpError) as caught:
        dry_run(store, parse_paste(fenced([op])))
    assert isinstance(caught.value.cause, UpdatePathError)


def test_supersede_touches_both_decisions(
    project: Project,
    make_item: Callable[..., Item],
    fenced: Callable[..., str],
    paste: Callable[[str], PasteResult],
) -> None:
    """A supersede reports the older decision's status change and final state."""
    goal = make_item(project, ItemKind.GOAL)
    ops = [
        {"op": "decision_record", "ref": "a", "owner": goal.key, "title": "a",
         "body": "", "status": "locked"},
        {"op": "decision_record", "owner": goal.key, "title": "b", "body": "",
         "status": "locked", "supersedes": "$a"},
    ]  # fmt: skip
    result = paste(fenced(ops))
    assert [(d.key, d.status) for d in result.decisions] == [
        ("goal-1/decision-1", "superseded"),
        ("goal-1/decision-2", "locked"),
    ]


@pytest.mark.usefixtures("project")
def test_unknown_project_lists_known_names(
    store: Store, fenced: Callable[..., str]
) -> None:
    """The block's project must be registered; the error lists real names."""
    block = parse_paste(fenced([{"op": "item_create", "kind": "goal", "title": "g"}],
                               project="nope"))  # fmt: skip
    with pytest.raises(PasteError, match="known names: xo, xoot"):
        dry_run(store, block)


@pytest.mark.usefixtures("work_tree")
def test_unknown_or_foreign_keys_are_named_safely(
    store: Store, fenced: Callable[..., str]
) -> None:
    """A key naming nothing is echoed; one of another project is refused."""
    missing = [{"op": "capture", "found_on": "goal-9", "title": "c"}]
    with pytest.raises(PasteOpError) as caught:
        dry_run(store, parse_paste(fenced(missing)))
    assert "goal-9" in error_message(caught.value)
    foreign = [{"op": "capture", "found_on": "nova:goal-1", "title": "c"}]
    with pytest.raises(PasteOpError) as caught:
        dry_run(store, parse_paste(fenced(foreign)))
    assert "QualifierError" in error_message(caught.value)
