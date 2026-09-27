"""B4: public keys resolve to rows without the MCP server, raising XootErrors."""

from collections.abc import Callable

import pytest

from xoot.exceptions.not_found_error import NotFoundError
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.event.entity_type import EntityType
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.models.project.project_registration import ProjectRegistration
from xoot.models.session.session import Session
from xoot.services import key_resolver
from xoot.services.decision_service import create_decision
from xoot.services.project_service import register_project
from xoot.store.store import Store


def test_every_kind_of_key(
    store: Store,
    project: Project,
    ctx: WriteContext,
    make_item: Callable[..., Item],
    make_session: Callable[..., Session],
) -> None:
    """Items, decisions, sessions and prefixes resolve, alone and via entity_by_key."""
    item = make_item(project, ItemKind.GOAL)
    decision = create_decision(store, project.id, DecisionCreate(title="d"), ctx)
    session = make_session(project)
    with store.read() as conn:
        assert key_resolver.item_by_key(conn, "xoot-1").id == item.id
        assert key_resolver.decision_by_key(conn, "xoot-D1").id == decision.id
        assert key_resolver.session_by_key(conn, "xoot-S1").id == session.id
        assert key_resolver.project_by_key(conn, "xoot").id == project.id
        resolved = [
            key_resolver.entity_by_key(conn, key)
            for key in ("xoot-1", "xoot-D1", "xoot-S1", "xoot")
        ]
    assert resolved == [
        (EntityType.ITEM, item.id),
        (EntityType.DECISION, decision.id),
        (EntityType.SESSION, session.id),
        (EntityType.PROJECT, project.id),
    ]


@pytest.mark.parametrize(
    ("key", "ref"),
    [
        ("xoot-99", "xoot-99"),
        ("zz-S1", "zz-S1"),
        ("NOT A KEY\x1b[2J", "malformed key"),
        ("xo", "malformed key"),
    ],
)
@pytest.mark.usefixtures("project")
def test_unknown_keys_do_not_echo_input(store: Store, key: str, ref: str) -> None:
    """Only a well-formed key is kept on the error; an alias is not a key."""
    with store.read() as conn:
        with pytest.raises(NotFoundError) as caught:
            key_resolver.entity_by_key(conn, key)
    assert caught.value.ref == ref


def test_a_record_key_wins_over_a_look_alike_prefix(
    store: Store, project: Project, ctx: WriteContext, make_item: Callable[..., Item]
) -> None:
    """A prefix shaped like an item key resolves only when no item matches."""
    lookalike = register_project(
        store, ProjectRegistration(key_prefix="xoot-1", name="n"), ctx.actor
    )
    with store.read() as conn:
        assert key_resolver.entity_by_key(conn, "xoot-1") == (
            EntityType.PROJECT,
            lookalike.id,
        )
    item = make_item(project, ItemKind.GOAL)
    with store.read() as conn:
        assert key_resolver.entity_by_key(conn, "xoot-1") == (EntityType.ITEM, item.id)
