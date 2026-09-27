"""A2: plan entries and create events digest a body through one helper."""

from collections.abc import Callable

from xoot.models.event.entity_type import EntityType
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.repositories.event import event_db
from xoot.services.plan_entries import item_entry
from xoot.store.store import Store
from xoot.utils.utils import body_digest

BODY = "caf\u00e9 body \U0001f600 " * 50


def test_plan_entry_and_create_event_agree(
    store: Store, project: Project, make_item: Callable[..., Item]
) -> None:
    """The same non-ASCII body digests identically in both records."""
    item = make_item(project, ItemKind.GOAL, body=BODY)
    with store.read() as conn:
        entry = item_entry(conn, item, {})
        created = event_db.list_for_entity(conn, EntityType.ITEM, item.id)[0]
    assert entry.body_sha256 == created.after["body_sha256"] == body_digest(BODY)
    assert body_digest("") != body_digest(" ")
