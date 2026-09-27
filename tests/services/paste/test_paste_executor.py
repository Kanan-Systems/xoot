"""
Executing a block: one transaction and one scope for the whole block. The
dry run persists nothing; any op failure refuses the whole block; the apply
commits only when its result digests the same as the dry run's. Writes are
Claude's through client paste.
"""

from collections.abc import Callable
from typing import Any

import pytest

from xoot.cli.render.errors import error_message
from xoot.exceptions.paste_error import PasteError
from xoot.exceptions.paste_op_error import PasteOpError
from xoot.exceptions.update_path_error import UpdatePathError
from xoot.exceptions.version_conflict_error import VersionConflictError
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.entity_type import EntityType
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.item.item_update import ItemUpdate
from xoot.models.project.project import Project
from xoot.models.session.client import Client
from xoot.models.session.disposition import Disposition
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.models.session.session_start import SessionStart
from xoot.repositories.event import event_db
from xoot.repositories.item import item_db
from xoot.repositories.session import session_db
from xoot.services.item_service import get_item, update_item
from xoot.services.paste.executor import (
    PLAN_CHANGED,
    apply,
    dry_run,
    result_digest,
)
from xoot.services.paste.models.paste_result import PasteResult
from xoot.services.paste.parser import parse_paste
from xoot.services.session_close_service import close_session
from xoot.services.session_service import start_session
from xoot.store.store import Store

START = {"op": "session_start", "title": "plan"}
FULL_BLOCK = [
    START,
    {"op": "item_create", "ref": "g", "kind": "goal", "title": "goal"},
    {"op": "item_create", "ref": "b", "kind": "batch", "title": "b", "parent": "$g"},
    {"op": "capture", "title": "side note", "body": "later"},
    {"op": "item_update", "key": "$b", "changes": {"state": "active"}},
    {
        "op": "decision_record",
        "ref": "d",
        "title": "use sqlite",
        "body": "local only",
        "status": "locked",
        "scope": "$g",
    },
    {"op": "decision_update", "key": "$d", "changes": {"status": "deferred"}},
    {
        "op": "session_close",
        "summary": "planned",
        # capture takes no ref, so its item is named by the key it will get.
        "dispositions": {
            "$g": "carry_over",
            "$b": "project_backlog",
            "xoot-3": "dropped",
        },
    },
]


@pytest.fixture(name="linked_goal")
def fixture_linked_goal(
    project: Project,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
) -> Item:
    """xoot-1, a goal linked to the open session xoot-S1."""
    item = make_item(project, ItemKind.GOAL)
    make_session(project, item.id)
    return item


@pytest.fixture(name="parked")
def fixture_parked(
    project: Project,
    store: Store,
    user: Actor,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
) -> Item:
    """xoot-1, parked in the backlog of xoot-S1, which is closed."""
    item = make_item(project, ItemKind.SUBTASK)
    first = make_session(project, item.id)
    request = SessionClose(dispositions={item.id: Disposition.SESSION_BACKLOG})
    close_session(store, first.id, request, user)
    return get_item(store, item.id)


@pytest.fixture(name="parent_batch")
def fixture_parent_batch(project: Project, make_item: Callable[..., Item]) -> Item:
    """A batch under a goal, with one subtask."""
    batch = make_item(
        project, ItemKind.BATCH, parent_id=make_item(project, ItemKind.GOAL).id
    )
    make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
    return batch


@pytest.fixture(name="sessions")
def fixture_sessions(
    project: Project, other_project: Project, store: Store, user: Actor
) -> None:
    """xoot-S1 is closed; nova-S1 is open."""
    closed = start_session(store, project.id, SessionStart(title="s"), user).session
    close_session(store, closed.id, SessionClose(), user)
    start_session(store, other_project.id, SessionStart(title="s"), user)


def test_dry_run_persists_nothing(
    project: Project,
    store: Store,
    fenced: Callable[..., str],
    snapshot: Callable[[], dict[str, Any]],
) -> None:
    """Rows, the dump, sqlite_sequence and the counters are all untouched."""
    before = snapshot()
    result = dry_run(store, parse_paste(fenced(FULL_BLOCK)))
    assert snapshot() == before
    assert result.session == "xoot-S1" and project.key_prefix == "xoot"
    assert [o.key for o in result.outcomes][:4] == [
        "xoot-S1",
        "xoot-1",
        "xoot-2",
        "xoot-3",
    ]


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
        START,
        {"op": "item_create", "ref": "g", "kind": "goal", "title": "goal"},
        {"op": "item_update", "key": "$g", "changes": {"state": "no_such_state"}},
        {"op": "capture", "title": "c"},
        {"op": "capture", "title": "d"},
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


def test_plan_changed_by_an_out_of_band_write_is_refused(
    store: Store,
    ctx: WriteContext,
    linked_goal: Item,
    fenced: Callable[..., str],
    snapshot: Callable[[], dict[str, Any]],
) -> None:
    """A disposed item changes between preview and apply: nothing is written."""
    ops = [
        {"op": "decision_record", "title": "d", "body": "", "status": "locked"},
        {"op": "session_close", "dispositions": {linked_goal.key: "carry_over"}},
    ]
    block = parse_paste(fenced(ops, session="xoot-S1"))
    preview = dry_run(store, block)
    update_item(store, linked_goal.id, 1, ItemUpdate(title="renamed"), ctx)
    before = snapshot()
    with pytest.raises(PasteError, match=f"^{PLAN_CHANGED}$"):
        apply(store, block, result_digest(preview))
    assert snapshot() == before
    assert session_db.get(store.conn, 1).status == "open"


def test_plan_changed_by_a_new_key_is_refused(
    project: Project,
    store: Store,
    make_item: Callable[..., Item],
    fenced: Callable[..., str],
) -> None:
    """Another writer takes the next number: the previewed keys would be wrong."""
    block = parse_paste(fenced([START, {"op": "capture", "title": "c"}]))
    preview = dry_run(store, block)
    make_item(project, ItemKind.GOAL)
    with pytest.raises(PasteError, match=f"^{PLAN_CHANGED}$"):
        apply(store, block, result_digest(preview))


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
        dry_run(store, parse_paste(fenced([START, update])))
    assert isinstance(caught.value.cause, VersionConflictError)
    assert error_message(caught.value) == (
        "error: PasteOpError: op 2 (item_update): VersionConflictError: xoot-1 "
        "is at version 2; changed since your version: title; by: user/cli"
    )


def test_events_are_claude_through_paste(
    project: Project,
    store: Store,
    fenced: Callable[..., str],
    paste: Callable[[str], PasteResult],
) -> None:
    """Every event is actor claude, client paste; the new session is paste's."""
    paste(fenced(FULL_BLOCK))
    with store.read() as conn:
        events = event_db.list_for_project(conn, project.id)
        session = session_db.get(conn, 1)
    ours = [e for e in events if e.session_id is not None]
    assert ours and {(e.actor_kind, e.client) for e in ours} == {
        (ActorKind.CLAUDE, Client.PASTE)
    }
    assert session is not None and session.client is Client.PASTE
    assert len({e.created_at for e in ours}) == 1


def test_existing_session_of_another_client_records_paste(
    project: Project,
    store: Store,
    claude: Actor,
    fenced: Callable[..., str],
    paste: Callable[[str], PasteResult],
) -> None:
    """A Claude Code session stays code; the paste's own events say paste."""
    start_session(store, project.id, SessionStart(title="code"), claude)
    paste(fenced([{"op": "capture", "title": "c"}], session="xoot-S1"))
    with store.read() as conn:
        session = session_db.get(conn, 1)
        item = item_db.get_by_key(conn, "xoot-1")
        events = event_db.list_for_project(conn, project.id)
    assert session is not None and session.client is Client.CODE
    assert item is not None
    created = [e for e in events if e.entity_type == "item"]
    assert [(e.actor_kind, e.client) for e in created] == [
        (ActorKind.CLAUDE, Client.PASTE)
    ]


def test_auto_backlog_moves_are_side_effects(
    store: Store,
    parked: Item,
    fenced: Callable[..., str],
    paste: Callable[[str], PasteResult],
) -> None:
    """Closing retires an earlier closed session's backlog, as the system."""
    close = {"op": "session_close", "dispositions": {}}
    result = paste(fenced([START, close]))
    assert [(m.key, m.origin_session) for m in result.auto_backlog] == [
        (parked.key, "xoot-S1")
    ]
    after = get_item(store, parked.id)
    assert after.backlog_session_id is None
    assert [(i.key, i.version) for i in result.items] == [(parked.key, after.version)]
    with store.read() as conn:
        events = event_db.list_for_entity(conn, EntityType.ITEM, parked.id)
    assert (events[-1].actor_kind, events[-1].client) == (
        ActorKind.SYSTEM,
        Client.PASTE,
    )


def test_subtree_drop_and_reparent_need_no_token(
    project: Project,
    store: Store,
    make_item: Callable[..., Item],
    fenced: Callable[..., str],
    paste: Callable[[str], PasteResult],
) -> None:
    """The confirmed dry run replaces the confirm token for subtree changes."""
    goal = make_item(project, ItemKind.GOAL)
    batch = make_item(project, ItemKind.BATCH, parent_id=goal.id)
    sub = make_item(project, ItemKind.SUBTASK, parent_id=batch.id)
    other = make_item(project, ItemKind.GOAL)
    ops = [
        START,
        {
            "op": "item_update",
            "key": batch.key,
            "expected_version": 1,
            "changes": {"parent": other.key},
        },
        {
            "op": "item_update",
            "key": other.key,
            "expected_version": 1,
            "changes": {"state": "dropped"},
        },
    ]
    result = paste(fenced(ops))
    assert result.outcomes[1].carried == (sub.key,)
    dropped = {c.key for c in result.outcomes[2].changes if c.field == "state"}
    assert dropped == {other.key, batch.key, sub.key}
    assert get_item(store, batch.id).parent_id == other.id
    assert get_item(store, sub.id).state == "dropped"


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"parent": None, "title": "t"}, "parent"),
        ({"state": "dropped", "title": "t"}, "a drop of an item with children"),
    ],
)
def test_alone_rules_match_the_tool(
    store: Store,
    parent_batch: Item,
    fenced: Callable[..., str],
    changes: dict[str, Any],
    field: str,
) -> None:
    """A parent change or a drop of a parent must be the only change."""
    update = {
        "op": "item_update",
        "key": parent_batch.key,
        "expected_version": 1,
        "changes": changes,
    }
    with pytest.raises(PasteOpError) as caught:
        dry_run(store, parse_paste(fenced([START, update])))
    assert isinstance(caught.value.cause, UpdatePathError)
    assert error_message(caught.value).endswith(
        f"UpdatePathError: {field} must be the only field in changes; send the "
        "other changes in a separate item_update call"
    )


@pytest.mark.usefixtures("project")
def test_supersede_touches_both_decisions(
    fenced: Callable[..., str], paste: Callable[[str], PasteResult]
) -> None:
    """The older decision's status change is part of the result."""
    old = {
        "op": "decision_record",
        "ref": "a",
        "title": "a",
        "body": "",
        "status": "locked",
    }
    new = {**old, "ref": "b", "supersedes": "$a"}
    result = paste(fenced([START, old, new]))
    assert [(d.key, d.status, d.version) for d in result.decisions] == [
        ("xoot-D1", "superseded", 2),
        ("xoot-D2", "locked", 1),
    ]


def test_missing_dispositions_are_listed(
    store: Store, linked_goal: Item, fenced: Callable[..., str]
) -> None:
    """A close that leaves a linked item without a disposition names it."""
    close = {"op": "session_close", "dispositions": {}}
    with pytest.raises(
        PasteOpError,
        match=rf"^op 1 \(session_close\): missing dispositions: {linked_goal.key}$",
    ):
        dry_run(store, parse_paste(fenced([close], session="xoot-S1")))


@pytest.mark.parametrize(
    ("session", "message"),
    [
        ("xoot-S9", "^session not found: xoot-S9$"),
        ("nova-S1", "^session nova-S1 belongs to another project$"),
        ("xoot-S1", "^session xoot-S1 is not open$"),
    ],
)
@pytest.mark.usefixtures("sessions")
def test_named_session_must_be_open_and_ours(
    store: Store, fenced: Callable[..., str], session: str, message: str
) -> None:
    """The block's session must be an open session of its project."""
    ops = [{"op": "capture", "title": "c"}]
    with pytest.raises(PasteError, match=message):
        dry_run(store, parse_paste(fenced(ops, session=session)))


@pytest.mark.usefixtures("project")
def test_unknown_project_lists_known_names(
    store: Store, fenced: Callable[..., str]
) -> None:
    """Only stored names are listed, never the name asked for."""
    with pytest.raises(
        PasteError, match="^project not resolved; known names: xo, xoot$"
    ):
        dry_run(store, parse_paste(fenced([START], project="nope")))


def test_unknown_key_is_named_safely(
    store: Store, fenced: Callable[..., str], project: Project
) -> None:
    """A well-formed missing key is repeated; a malformed one is not."""
    for key, shown in (("xoot-99", "'xoot-99'"), ("bad key!", "'malformed key'")):
        update = {"op": "item_update", "key": key, "expected_version": 1, "changes": {}}
        with pytest.raises(PasteOpError) as caught:
            dry_run(store, parse_paste(fenced([START, update])))
        assert error_message(caught.value) == (
            f"error: PasteOpError: op 2 (item_update): NotFoundError: item {shown} not found"
        )
    assert project.id == 1
