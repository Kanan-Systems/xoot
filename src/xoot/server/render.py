"""
Rendering domain rows as tool outputs.

Stored ids become public keys through a KeyBook, internal columns are
dropped, and bodies never appear in event or change diffs.
"""

import sqlite3
from typing import Any

from xoot.models.decision.decision import Decision
from xoot.models.event.event import Event
from xoot.models.fields import format_timestamp
from xoot.models.item.completion_report import CompletionReport
from xoot.models.item.item import Item
from xoot.models.item.item_change import ItemChange
from xoot.models.item.tree_result import TreeResult
from xoot.models.project.project import Project
from xoot.models.workflow.category import Category
from xoot.repositories.item import item_alias_db
from xoot.server.errors import PUBLIC_NAMES
from xoot.server.key_book import KeyBook
from xoot.server.schemas.blocked_entry import BlockedEntry
from xoot.server.schemas.change_entry import ChangeEntry
from xoot.server.schemas.children_summary import ChildrenSummary
from xoot.server.schemas.decision_detail import DecisionDetail
from xoot.server.schemas.decision_summary import DecisionSummary
from xoot.server.schemas.event_entry import EventEntry
from xoot.server.schemas.item_detail import ItemDetail
from xoot.server.schemas.item_summary import ItemSummary
from xoot.server.schemas.item_write_output import ItemWriteOutput
from xoot.server.schemas.tree_entry import TreeEntry
from xoot.server.schemas.version_entry import VersionEntry

_INTERNAL = frozenset({"id", "project_id", "number"})
_BODY = frozenset({"body", "body_sha256", "body_len"})
_ITEM_REFS = frozenset(
    {
        "parent_id", "owner_item_id", "item_id", "found_on_item_id",
        "covered_by_item_id", "origin_item_id",
    }
)  # fmt: skip
_DECISION_REFS = frozenset({"awaiting_decision_id", "supersedes_id"})


def completion(report: CompletionReport) -> dict[str, Any]:
    """
    Render a completion report as the fields every write output carries.

    Args:
        - report (CompletionReport): what the engine did in the write.

    Returns:
        - fields (dict[str, Any]): completed, reopened, blocked and changed.
    """
    return {
        "completed": list(report.completed),
        "reopened": list(report.reopened),
        "blocked": [
            BlockedEntry(key=b.key, open_backlog=b.open_backlog) for b in report.blocked
        ],
        "changed": [
            VersionEntry(key=c.key, version=c.version, state=c.state)
            for c in report.changed
        ],
    }


def item_write_output(
    conn: sqlite3.Connection, project: Project, item: Item, report: CompletionReport
) -> ItemWriteOutput:
    """
    Render the result of a write that created one item.

    Args:
        - conn (sqlite3.Connection): a connection inside a read transaction.
        - project (Project): the item's project.
        - item (Item): the new item.
        - report (CompletionReport): what the completion engine did.

    Returns:
        - output (ItemWriteOutput): the item and the completion outcome.
    """
    return ItemWriteOutput(
        project=project.key_prefix,
        item=item_detail(KeyBook(conn), item),
        **completion(report),
    )


def item_summary(book: KeyBook, item: Item) -> ItemSummary:
    """
    Render an item for a list.

    Args:
        - book (KeyBook): lookups for the current transaction.
        - item (Item): the item.

    Returns:
        - summary (ItemSummary): the rendered item.
    """
    return ItemSummary(
        key=item.key,
        kind=item.kind,
        title=item.title,
        state=item.state,
        category=book.category(item),
        parent=book.item_key(item.parent_id),
        version=item.version,
    )


def tree_entries(book: KeyBook, result: TreeResult) -> list[TreeEntry]:
    """
    Render a tree query's nodes, keeping their pre-order.

    Args:
        - book (KeyBook): lookups for the current transaction.
        - result (TreeResult): the query result.

    Returns:
        - entries (list[TreeEntry]): one entry per node.
    """
    return [
        TreeEntry(depth=node.depth, item=item_summary(book, node.item))
        for node in result.nodes
    ]


def children_summary(
    book: KeyBook, children: list[Item], limit: int
) -> ChildrenSummary:
    """
    Summarize an item's direct children: counts per category and the first
    few of them.

    Args:
        - book (KeyBook): lookups for the current transaction.
        - children (list[Item]): every direct child, work first.
        - limit (int): the most children to list.

    Returns:
        - summary (ChildrenSummary): the counts, the listed children and
          whether the list was cut.
    """
    by_category: dict[Category, int] = {}
    for child in children:
        category = book.category(child)
        if category is not None:
            by_category[category] = by_category.get(category, 0) + 1
    return ChildrenSummary(
        total=len(children),
        by_category=by_category,
        items=[item_summary(book, child) for child in children[:limit]],
        truncated=len(children) > limit,
    )


def item_detail(book: KeyBook, item: Item) -> ItemDetail:
    """
    Render one item in full, with every old key that still resolves to it.

    Args:
        - book (KeyBook): lookups for the current transaction.
        - item (Item): the item.

    Returns:
        - detail (ItemDetail): the rendered item.
    """
    return ItemDetail(
        **item_summary(book, item).model_dump(),
        body=item.body,
        awaiting_decision=book.decision_key(item.awaiting_decision_id),
        found_on=book.item_key(item.found_on_item_id),
        covered_by=book.item_key(item.covered_by_item_id),
        origin=book.item_key(item.origin_item_id),
        aliases=_aliases(book.conn, item),
        created_at=format_timestamp(item.created_at),
        updated_at=format_timestamp(item.updated_at),
    )


def decision_summary(book: KeyBook, decision: Decision) -> DecisionSummary:
    """
    Render a decision for a list.

    Args:
        - book (KeyBook): lookups for the current transaction.
        - decision (Decision): the decision.

    Returns:
        - summary (DecisionSummary): the rendered decision.
    """
    return DecisionSummary(
        key=decision.key,
        title=decision.title,
        status=decision.status,
        owner=book.item_key(decision.owner_item_id),
        supersedes=book.decision_key(decision.supersedes_id),
        version=decision.version,
        updated_at=format_timestamp(decision.updated_at),
    )


def decision_detail(book: KeyBook, decision: Decision) -> DecisionDetail:
    """
    Render one decision in full.

    Args:
        - book (KeyBook): lookups for the current transaction.
        - decision (Decision): the decision.

    Returns:
        - detail (DecisionDetail): the rendered decision.
    """
    return DecisionDetail(
        **decision_summary(book, decision).model_dump(),
        body=decision.body,
        created_at=format_timestamp(decision.created_at),
    )


def change_entry(book: KeyBook, change: ItemChange) -> ChangeEntry:
    """
    Render a planned or applied item change.

    A move's number stays in: it is the number the item takes under its new
    parent, which a push preview must show.

    Args:
        - book (KeyBook): lookups for the current transaction.
        - change (ItemChange): the change.

    Returns:
        - entry (ChangeEntry): the change with keys for references.
    """
    return ChangeEntry(
        key=change.key,
        before=_with_number(public_fields(book, change.before), change.before),
        after=_with_number(public_fields(book, change.after), change.after),
    )


def _with_number(public: dict[str, Any] | None, raw: dict[str, Any]) -> dict[str, Any]:
    if "number" not in raw:
        return public or {}
    return {**(public or {}), "number": raw["number"]}


def event_entry(book: KeyBook, event: Event) -> EventEntry:
    """
    Render one event, without body content.

    Args:
        - book (KeyBook): lookups for the current transaction.
        - event (Event): the event.

    Returns:
        - entry (EventEntry): the rendered event.
    """
    names = {**(event.before or {}), **(event.after or {})}
    changed = sorted(
        {"body" if name in _BODY else PUBLIC_NAMES.get(name, name) for name in names}
        - _INTERNAL
    )
    return EventEntry(
        action=event.action,
        actor_kind=event.actor_kind,
        client=event.client,
        created_at=format_timestamp(event.created_at),
        redacted=event.redacted_at is not None,
        changed=changed,
        before=public_fields(book, event.before),
        after=public_fields(book, event.after),
    )


def public_fields(
    book: KeyBook, values: dict[str, Any] | None
) -> dict[str, Any] | None:
    """
    Drop internal and body fields and turn reference ids into keys.

    Args:
        - book (KeyBook): lookups for the current transaction.
        - values (dict[str, Any] | None): a stored diff or snapshot.

    Returns:
        - fields (dict[str, Any] | None): the public view, or None for None.
    """
    if values is None:
        return None
    public: dict[str, Any] = {}
    for name, value in values.items():
        if name in _INTERNAL or name in _BODY:
            continue
        public[PUBLIC_NAMES.get(name, name)] = _reference(book, name, value)
    return public


def _reference(book: KeyBook, name: str, value: Any) -> Any:
    if name in _ITEM_REFS:
        return book.item_key(value)
    if name in _DECISION_REFS:
        return book.decision_key(value)
    return value


def _aliases(conn: sqlite3.Connection, item: Item) -> list[str]:
    return item_alias_db.list_for_item(conn, item.id)
