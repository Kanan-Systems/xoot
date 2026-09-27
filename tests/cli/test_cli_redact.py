"""
T7: redaction through the CLI rewrites the row and its events, empties
confirm_token, and leaves no byte of the old text in the database or WAL.
"""

from collections.abc import Callable
from typing import Any

import pytest

from xoot.cli.render.results import render_redaction
from xoot.models.event.actor import Actor
from xoot.models.event.entity_type import EntityType
from xoot.models.event.redactable_field import RedactableField
from xoot.models.event.redaction_result import RedactionResult
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.project.project_registration import ProjectRegistration
from xoot.models.session.session import Session
from xoot.repositories.event import event_db
from xoot.services.confirm_service import issue_token
from xoot.services.item_service import get_item
from xoot.services.project_service import get_project, register_project
from xoot.services.redaction_service import REDACTED
from xoot.store.store import Store

DIGEST = "c" * 64


@pytest.fixture(name="pending_token")
def fixture_pending_token(
    store: Store, project: Project, make_session: Callable[..., Session]
) -> None:
    """An unused confirm token of an open session."""
    issue_token(store, make_session(project).id, "session_close", DIGEST, DIGEST)


@pytest.mark.usefixtures("pending_token")
@pytest.mark.parametrize("field", ["title", "body"])
def test_redact_item_field(
    xoot: Any,
    store: Store,
    secret_item: Item,
    disk_hits: Callable[[str], int],
    field: str,
) -> None:
    """Row, events, tokens and raw bytes are all clean afterwards."""
    marker = getattr(secret_item, field)
    assert disk_hits(marker) > 0
    run = xoot("redact", secret_item.key, field, "--yes")
    assert run.code == 0, run.err
    assert run.out == (
        f"redacted {field} of item {secret_item.key}, now version 2; "
        "1 event rewritten\n"
    )
    assert getattr(get_item(store, secret_item.id), field) == REDACTED
    with store.read() as conn:
        events = event_db.list_for_entity(conn, EntityType.ITEM, secret_item.id)
        tokens = conn.execute("SELECT count(*) FROM confirm_token").fetchone()[0]
    assert all(marker not in str((e.before, e.after)) for e in events)
    assert events[-1].action == "redact" and events[-1].after == {
        "field": field,
        "version": 2,
    }
    assert tokens == 0
    assert disk_hits(marker) == 0


def test_redact_project_name_by_prefix(
    xoot: Any, store: Store, disk_hits: Callable[[str], int]
) -> None:
    """KEY may be a project prefix, with FIELD name."""
    secret = "project-name-secret-51c2"
    assert xoot("init", "/work/p", "--prefix", "leaky", "--name", secret).code == 0
    assert disk_hits(secret) > 0
    run = xoot("redact", "leaky", "name", "--yes")
    assert run.code == 0, run.err
    with store.read() as conn:
        project_id = conn.execute(
            "SELECT id FROM project WHERE key_prefix = 'leaky'"
        ).fetchone()[0]
    assert get_project(store, project_id).name == REDACTED
    assert disk_hits(secret) == 0


@pytest.mark.usefixtures("secret_item")
@pytest.mark.parametrize(
    ("argv", "error"),
    [
        (["xoot-99", "title"], "error: NotFoundError: record 'xoot-99' not found\n"),
        (
            ["x\x1b[2J", "title"],
            "error: NotFoundError: record 'malformed key' not found\n",
        ),
        (
            ["xoot", "title"],
            "error: RedactionError: cannot redact project field title\n",
        ),
        (
            ["xoot-1", "summary"],
            "error: RedactionError: cannot redact item field summary\n",
        ),
    ],
)
def test_refused_before_any_prompt(
    xoot: Any, row_counts: Any, argv: list[str], error: str
) -> None:
    """Unknown keys and impossible fields are refused without asking."""
    before = row_counts()
    run = xoot("redact", *argv, answer="y")
    assert (run.code, run.out, run.err) == (1, "", error)
    assert row_counts() == before


@pytest.fixture(name="lookalike")
def fixture_lookalike(
    store: Store, user: Actor, make_item: Callable[..., Item]
) -> tuple[Project, Item, Project]:
    """L11: project ab with item 12, and project cd whose alias is "ab-12"."""
    ab = register_project(store, ProjectRegistration(key_prefix="ab", name="ab"), user)
    cd = register_project(
        store,
        ProjectRegistration(key_prefix="cd", name="cd", aliases=("ab-12",)),
        user,
    )
    items = [make_item(ab, ItemKind.GOAL, title=f"t{n}") for n in range(1, 13)]
    return ab, items[-1], cd


@pytest.mark.parametrize(
    "case",
    [("ab-12", "title", "item"), ("ab", "name", "ab"), ("cd", "name", "cd")],
    ids=["item-key", "prefix-ab", "prefix-cd"],
)
def test_key_with_a_dash_is_an_entity_key(
    xoot: Any,
    store: Store,
    lookalike: tuple[Project, Item, Project],
    case: tuple[str, str, str],
) -> None:
    """L11: each KEY redacts exactly the entity it names, never the alias owner."""
    key, field, target = case
    ab, item, cd = lookalike
    run = xoot("redact", key, field, "--yes")
    assert run.code == 0, run.err
    redacted = {
        "item": get_item(store, item.id).title == REDACTED,
        "ab": get_project(store, ab.id).name == REDACTED,
        "cd": get_project(store, cd.id).name == REDACTED,
    }
    assert redacted == {name: name == target for name in redacted}
    assert get_item(store, item.id - 1).title == "t11"


@pytest.mark.parametrize(
    ("event_ids", "count"), [((), "0 events"), ((7,), "1 event"), ((7, 8), "2 events")]
)
def test_event_count_is_pluralized(event_ids: tuple[int, ...], count: str) -> None:
    """One event is "1 event"; every other count is "N events"."""
    result = RedactionResult(
        entity_type=EntityType.PROJECT,
        entity_id=1,
        field=RedactableField.NAME,
        version=None,
        redacted_event_ids=event_ids,
        purged=True,
    )
    assert render_redaction(result, "ab") == (
        f"redacted name of project ab; {count} rewritten"
    )
