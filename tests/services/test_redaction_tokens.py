"""
A redaction deletes every confirm token in its own transaction, used or
not, since a stored plan digest could confirm a guess at redacted text.
"""

from collections.abc import Callable

import pytest

from xoot.exceptions.redaction_error import RedactionError
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project import Project
from xoot.services.confirm_service import issue_token
from xoot.services.redaction_service import redact_field
from xoot.store.store import Store

DIGEST = "a" * 64


def _tokens(store: Store) -> int:
    with store.read() as conn:
        return conn.execute("SELECT count(*) FROM confirm_token").fetchone()[0]


def test_redaction_deletes_every_token(
    store: Store,
    project: Project,
    ctx: WriteContext,
    make_item: Callable[..., Item],
    other_project: Project,
) -> None:
    """Unused tokens of several projects and tools are all gone afterwards."""
    item = make_item(project, ItemKind.GOAL, title="short secret")
    for tool in ("backlog_push", "items_create_bulk"):
        for owner in (project, other_project):
            issue_token(store, owner.id, tool, DIGEST, DIGEST, actor=ctx.actor)
    assert _tokens(store) == 4
    redact_field(store, "item", item.id, "title", ctx.actor)
    assert _tokens(store) == 0


def test_refused_redaction_keeps_the_tokens(
    store: Store,
    project: Project,
    ctx: WriteContext,
    make_item: Callable[..., Item],
) -> None:
    """The delete shares the redaction's transaction: a refusal rolls it back."""
    item = make_item(project, ItemKind.GOAL)
    issue_token(store, project.id, "backlog_push", DIGEST, DIGEST, actor=ctx.actor)
    with pytest.raises(RedactionError):
        redact_field(store, "item", item.id, "body", ctx.actor)
    assert _tokens(store) == 1
