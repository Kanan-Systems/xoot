"""E10: bulk create validates everything in a pure preview and applies all or nothing."""

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from xoot.exceptions.confirm_token_error import ConfirmTokenError
from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.exceptions.hierarchy_error import HierarchyError
from xoot.exceptions.session_state_error import SessionStateError
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.event.actor import Actor
from xoot.models.item.bulk_create import MAX_BULK_ITEMS, BulkCreate
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.models.session.session_close import SessionClose
from xoot.repositories.session import session_item_ref_db
from xoot.services.bulk_service import apply_bulk, preview_bulk
from xoot.services.confirm_service import issue_token
from xoot.services.session_close_service import close_session
from xoot.store.store import Store

DIGEST = "c" * 64


def _tree() -> BulkCreate:
    """goal > (batch > two subtasks), plus one unfiled subtask."""
    return BulkCreate.model_validate(
        {
            "items": [
                {
                    "kind": "goal",
                    "title": "g",
                    "children": [
                        {
                            "kind": "batch",
                            "title": "b",
                            "children": [
                                {"kind": "subtask", "title": "s1"},
                                {"kind": "subtask", "title": "s2", "body": "details"},
                            ],
                        }
                    ],
                },
                {"kind": "subtask", "title": "loose"},
            ]
        }
    )


@pytest.fixture(name="session")
def fixture_session(project: Project, make_session: Callable[..., Session]) -> Session:
    """An open session in the xoot project."""
    return make_session(project)


def test_preview_plans_keys_and_writes_nothing(
    store: Store, session: Session, row_counts: Callable[[], dict[str, int]]
) -> None:
    """The preview assigns keys in pre-order, with parent keys, and writes nothing."""
    before, changes = row_counts(), store.conn.total_changes
    plan = preview_bulk(store, session.id, _tree())
    assert (row_counts(), store.conn.total_changes) == (before, changes)
    assert [(p.key, p.kind, p.parent_key) for p in plan.items] == [
        ("xoot-1", ItemKind.GOAL, None),
        ("xoot-2", ItemKind.BATCH, "xoot-1"),
        ("xoot-3", ItemKind.SUBTASK, "xoot-2"),
        ("xoot-4", ItemKind.SUBTASK, "xoot-2"),
        ("xoot-5", ItemKind.SUBTASK, None),
    ]


def test_apply_creates_every_item_linked_to_the_session(
    store: Store, session: Session, claude: Actor
) -> None:
    """Apply inserts the planned tree in one go and links each item."""
    plan = preview_bulk(store, session.id, _tree())
    created = apply_bulk(store, session.id, _tree(), claude)
    assert [item.key for item in created] == [p.key for p in plan.items]
    by_title = {item.title: item for item in created}
    goal, batch = by_title["g"], by_title["b"]
    assert batch.parent_id == goal.id
    assert by_title["s1"].parent_id == by_title["s2"].parent_id == batch.id
    assert by_title["s2"].body == "details" and by_title["loose"].unfiled
    assert {item.state for item in created} == {"open"}
    with store.read() as conn:
        refs = session_item_ref_db.list_for_session(conn, session.id)
    assert {ref.item_id for ref in refs} == {item.id for item in created}


def test_existing_parent_is_used(
    store: Store,
    project: Project,
    session: Session,
    claude: Actor,
    make_item: Callable[..., Item],
) -> None:
    """A top-level node may name an existing parent of the right kind."""
    goal = make_item(project, ItemKind.GOAL)
    request = BulkCreate.model_validate(
        {"items": [{"kind": "batch", "title": "b", "parent_id": goal.id}]}
    )
    assert preview_bulk(store, session.id, request).items[0].parent_key == goal.key
    created = apply_bulk(store, session.id, request, claude)
    assert [item.parent_id for item in created] == [goal.id]


@pytest.mark.parametrize(
    "items",
    [
        [{"kind": "batch", "title": "no goal"}],
        [
            {
                "kind": "goal",
                "title": "g",
                "children": [{"kind": "subtask", "title": "s"}],
            }
        ],
        [
            {
                "kind": "subtask",
                "title": "s",
                "children": [{"kind": "subtask", "title": "t"}],
            }
        ],
    ],
)
def test_hierarchy_is_checked_before_anything_is_written(
    store: Store,
    session: Session,
    claude: Actor,
    items: list[dict[str, Any]],
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """Preview and apply both refuse a broken hierarchy; the apply writes nothing."""
    request = BulkCreate.model_validate({"items": items})
    with pytest.raises(HierarchyError):
        preview_bulk(store, session.id, request)
    before = row_counts()
    with pytest.raises(HierarchyError):
        apply_bulk(store, session.id, request, claude)
    assert row_counts() == before


@pytest.fixture(name="foreign")
def fixture_foreign(other_project: Project, make_item: Callable[..., Item]) -> Item:
    """A goal in another project."""
    return make_item(other_project, ItemKind.GOAL)


def test_late_failure_rolls_back_earlier_items(
    store: Store,
    session: Session,
    claude: Actor,
    foreign: Item,
    row_counts: Callable[[], dict[str, int]],
) -> None:
    """A bad node after good ones still leaves nothing behind."""
    request = BulkCreate.model_validate(
        {
            "items": [
                {"kind": "goal", "title": "fine"},
                {"kind": "batch", "title": "wrong project", "parent_id": foreign.id},
            ]
        }
    )
    before = row_counts()
    with pytest.raises(CrossProjectError):
        apply_bulk(store, session.id, request, claude)
    assert row_counts() == before
    assert preview_bulk(store, session.id, _tree()).items[0].key == "xoot-1"


@pytest.mark.parametrize(
    "items",
    [
        [{"kind": "subtask", "title": f"s{n}"} for n in range(MAX_BULK_ITEMS + 1)],
        [
            {
                "kind": "goal",
                "title": "g",
                "children": [{"kind": "batch", "title": "b", "parent_id": 1}],
            }
        ],
        [],
    ],
)
def test_request_shape_is_validated(items: list[dict[str, Any]]) -> None:
    """At most 50 items in total, at least one, and parent_id only at the top."""
    with pytest.raises(ValidationError):
        BulkCreate.model_validate({"items": items})


def test_nested_count_is_capped() -> None:
    """The cap counts nested nodes, not only top-level ones."""
    batch = {
        "kind": "batch",
        "title": "b",
        "children": [{"kind": "subtask", "title": "s"}] * 49,
    }
    with pytest.raises(ValidationError):
        BulkCreate.model_validate(
            {"items": [{"kind": "goal", "title": "g", "children": [batch]}]}
        )


def test_closed_session_is_refused(
    store: Store, session: Session, user: Actor, claude: Actor
) -> None:
    """Bulk creates need an open session."""
    close_session(store, session.id, SessionClose(), user)
    with pytest.raises(SessionStateError):
        preview_bulk(store, session.id, _tree())
    with pytest.raises(SessionStateError):
        apply_bulk(store, session.id, _tree(), claude)


def test_apply_consumes_its_token(
    store: Store, session: Session, claude: Actor
) -> None:
    """With a confirmation, the apply spends it; a replay is refused."""
    plan = preview_bulk(store, session.id, _tree())
    token = issue_token(
        store, session.id, "items_create_bulk", DIGEST, plan.plan_sha256
    )
    claim = Confirmation(token=token, tool="items_create_bulk", args_sha256=DIGEST)
    assert len(apply_bulk(store, session.id, _tree(), claude, claim)) == 5
    with pytest.raises(ConfirmTokenError, match="already been used"):
        apply_bulk(store, session.id, _tree(), claude, claim)
