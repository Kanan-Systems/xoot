"""
The subtree side of item_update: a resolved drop or reparent, and its output.

A SubtreeChange is chosen by the tool from a read snapshot; it previews or
applies itself, and plan_output renders the plan it returns, with every
changed or carried item read back after an apply.
"""

import sqlite3

from pydantic import BaseModel, ConfigDict

from xoot.models.confirm.confirmation import Confirmation
from xoot.models.event.write_context import WriteContext
from xoot.models.fields import Id, StateName
from xoot.models.item.subtree_plan import SubtreePlan
from xoot.repositories.item import item_db
from xoot.server.key_book import KeyBook
from xoot.server.render import change_entry
from xoot.server.schemas.affected_item_entry import AffectedItemEntry
from xoot.server.schemas.item_update_output import ItemUpdateOutput
from xoot.server.schemas.literals import Phase, UpdateMode
from xoot.server.schemas.subtree_output import SubtreeOutput
from xoot.services.subtree_service import (
    apply_drop_in,
    apply_reparent_in,
    preview_drop,
    preview_reparent,
)
from xoot.services.write_scope import WriteScope
from xoot.store.store import Store


class SubtreeChange(BaseModel):
    """One item's subtree drop or reparent, resolved and ready to preview or apply."""

    model_config = ConfigDict(frozen=True)

    mode: UpdateMode
    item_id: Id
    key: str
    new_parent_id: Id | None
    # The dropped state asked for; drop only.
    state: StateName | None
    expected_version: Id
    write: WriteContext

    def preview(self, store: Store) -> SubtreePlan:
        """
        Plan the change without writing.

        Args:
            - store (Store): the database.

        Returns:
            - plan (SubtreePlan): the planned changes.
        """
        if self.mode == "drop":
            return preview_drop(store, self.item_id, self.state)
        return preview_reparent(store, self.item_id, self.new_parent_id)

    def apply(self, store: Store, claim: Confirmation | None = None) -> SubtreePlan:
        """
        Write the change in its own transaction, consuming the token when one
        is given.

        Args:
            - store (Store): the database.
            - claim (Confirmation | None): the preview's token claim.

        Returns:
            - plan (SubtreePlan): the changes written.
        """
        with store.write() as conn:
            return self.apply_in(WriteScope(conn, self.write), claim)

    def apply_in(
        self, scope: WriteScope, claim: Confirmation | None = None
    ) -> SubtreePlan:
        """
        Write the change; the caller owns the transaction.

        Args:
            - scope (WriteScope): the open write scope.
            - claim (Confirmation | None): the preview's token claim.

        Returns:
            - plan (SubtreePlan): the changes written.
        """
        if self.mode == "drop":
            return apply_drop_in(
                scope, self.item_id, self.expected_version, claim, state=self.state
            )
        return apply_reparent_in(
            scope,
            self.item_id,
            self.new_parent_id,
            self.expected_version,
            confirm=claim,
        )


def plan_output(
    store: Store,
    request: SubtreeChange,
    phase: Phase,
    token: str | None,
    plan: SubtreePlan,
) -> ItemUpdateOutput:
    """
    Render a subtree plan as the item_update output.

    Args:
        - store (Store): the database.
        - request (SubtreeChange): the change the plan belongs to.
        - phase (Phase): preview or applied.
        - token (str | None): the confirm token of a preview.
        - plan (SubtreePlan): the planned or written changes.

    Returns:
        - output (ItemUpdateOutput): the plan, plus the affected items once
          applied.
    """
    with store.read() as conn:
        book = KeyBook(conn)
        keys = (book.item_key(item_id) for item_id in plan.carried_item_ids)
        output = SubtreeOutput(
            root=request.key,
            changes=[change_entry(book, change) for change in plan.changes],
            carried=[key for key in keys if key is not None],
        )
        items = None if phase == "preview" else _affected(conn, book, plan)
    return ItemUpdateOutput(
        mode=request.mode,
        phase=phase,
        confirm_token=token,
        item=None,
        items=items,
        plan=output,
    )


def _affected(
    conn: sqlite3.Connection, book: KeyBook, plan: SubtreePlan
) -> list[AffectedItemEntry]:
    """Every changed or carried item, read back after the write."""
    item_ids = [change.item_id for change in plan.changes]
    item_ids.extend(plan.carried_item_ids)
    rows = (item_db.get(conn, item_id) for item_id in item_ids)
    return [
        AffectedItemEntry(
            key=row.key,
            state=row.state,
            parent=book.item_key(row.parent_id),
            version=row.version,
        )
        for row in rows
        if row is not None
    ]
