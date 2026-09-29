"""
The state of one block's execution inside its write transaction.

Every op writes through the run's single WriteScope, so the whole block
shares one timestamp, one completion log, and commits or rolls back as one.
The actor is Claude and the client is paste. Keys resolve within the
block's project (a qualified key must name that project); refs resolve to
the current row of the record the block created.
"""

import sqlite3
from typing import Literal

from xoot.exceptions.not_found_error import NotFoundError
from xoot.exceptions.paste_error import PasteError
from xoot.exceptions.qualifier_error import QualifierError
from xoot.models.decision.decision import Decision
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.repositories.decision import decision_db
from xoot.repositories.item import item_db
from xoot.services import key_resolver
from xoot.services.lookups import require_decision, require_item
from xoot.services.paste.models.fields import is_ref, ref_name
from xoot.services.paste.models.paste_block import PasteBlock
from xoot.services.paste.models.paste_decision_state import PasteDecisionState
from xoot.services.paste.models.paste_item_state import PasteItemState
from xoot.services.paste.models.paste_label import PasteLabel
from xoot.services.paste.models.paste_op_outcome import PasteOpOutcome
from xoot.services.paste.models.paste_result import PasteResult
from xoot.services.project_resolver import by_name, known_names
from xoot.services.project_scope import CONFLICT, unqualified
from xoot.services.write_scope import WriteScope
from xoot.utils.keys import split_qualified

PASTE_ACTOR = Actor(kind=ActorKind.CLAUDE, client=Client.PASTE)

type Touched = tuple[Literal["item", "decision"], int]


class PasteRun:
    """
    One execution of a block: the scope every op writes through, the refs
    defined so far, and every item and decision the block touched, in
    first-touch order.
    """

    def __init__(self, conn: sqlite3.Connection, block: PasteBlock) -> None:
        """
        Resolve the block's project.

        Args:
            - conn (sqlite3.Connection): a connection inside a write transaction.
            - block (PasteBlock): the checked block.

        Raises:
            - PasteError: the project is unknown.
        """
        self.conn = conn
        found = by_name(conn, block.project)
        if found is None:
            names = ", ".join(known_names(conn)) or "none registered"
            raise PasteError(f"project not resolved; known names: {names}")
        self.project = found[0]
        self.scope = WriteScope(conn, WriteContext(actor=PASTE_ACTOR))
        self.refs: dict[str, Item | Decision] = {}
        # A dict as an ordered set: the result lists records in touch order.
        self._touched: dict[Touched, None] = {}

    def touch(self, row: Item | Decision) -> None:
        """
        Remember a record the block wrote.

        Args:
            - row (Item | Decision): the record.
        """
        self._touched["item" if isinstance(row, Item) else "decision", row.id] = None

    def created(
        self, index: int, op: str, row: Item | Decision, ref: str | None
    ) -> PasteOpOutcome:
        """
        Record a new item or decision and the ref naming it.

        Args:
            - index (int): the op's 1-based position.
            - op (str): the op name.
            - row (Item | Decision): the new record.
            - ref (str | None): the name later ops use for it.

        Returns:
            - outcome (PasteOpOutcome): the op's outcome.
        """
        self.touch(row)
        if ref is not None:
            self.refs[ref] = row
        return PasteOpOutcome(index=index, op=op, key=row.key, ref=ref, created=True)

    def item(self, value: str) -> Item:
        """
        Resolve an item key or ref to its current row.

        Args:
            - value (str): a key (qualified or not), or "$<ref>" of an item
              this block created.

        Returns:
            - item (Item): the current row.

        Raises:
            - NotFoundError: the key names no item, or the ref no item.
            - QualifierError: the key is qualified with another project.
        """
        if not is_ref(value):
            key = self._own_key(value)
            return key_resolver.item_by_key(self.conn, self.project.id, key)
        row = self.refs.get(ref_name(value) or "")
        if not isinstance(row, Item):
            raise NotFoundError("item ref", key_resolver.MALFORMED)
        return require_item(self.conn, row.id)

    def decision(self, value: str) -> Decision:
        """
        Resolve a decision key or ref to its current row.

        Args:
            - value (str): a key (qualified or not), or "$<ref>" of a
              decision this block recorded.

        Returns:
            - decision (Decision): the current row.

        Raises:
            - NotFoundError: the key names no decision, or the ref none.
            - QualifierError: the key is qualified with another project.
        """
        if not is_ref(value):
            key = self._own_key(value)
            return key_resolver.decision_by_key(self.conn, self.project.id, key)
        row = self.refs.get(ref_name(value) or "")
        if not isinstance(row, Decision):
            raise NotFoundError("decision ref", key_resolver.MALFORMED)
        return require_decision(self.conn, row.id)

    def result(self, outcomes: list[PasteOpOutcome]) -> PasteResult:
        """
        Read back every touched record and summarize the run.

        Args:
            - outcomes (list[PasteOpOutcome]): every op's outcome, in order.

        Returns:
            - result (PasteResult): the outcomes, refs, final records (every
              item whose version changed, the engine's writes included), the
              completion outcome, and the labels the plan shows.
        """
        items: list[PasteItemState] = []
        decisions: list[PasteDecisionState] = []
        labels: dict[str, PasteLabel] = {}
        for kind, row_id in self._touched:
            if kind == "item":
                item = item_db.get(self.conn, row_id)
                if item is not None:
                    items.append(
                        PasteItemState(
                            key=item.key, version=item.version, state=item.state
                        )
                    )
                    labels[item.key] = PasteLabel(kind=item.kind, title=item.title)
            else:
                decision = decision_db.get(self.conn, row_id)
                if decision is not None:
                    decisions.append(
                        PasteDecisionState(
                            key=decision.key,
                            version=decision.version,
                            status=decision.status,
                        )
                    )
                    labels[decision.key] = PasteLabel(
                        kind="decision", title=decision.title
                    )
        report = self.scope.report()
        # Goals and batches the completion engine wrote change version too;
        # the receipt lists them so the next block's expected_versions hold.
        listed = {state.key for state in items}
        for change in report.changed:
            if change.key not in listed:
                items.append(
                    PasteItemState(
                        key=change.key, version=change.version, state=change.state
                    )
                )
                listed.add(change.key)
        engine_keys = [
            *report.completed,
            *report.reopened,
            *(b.key for b in report.blocked),
        ]
        for key in engine_keys:
            row = item_db.get_by_key(self.conn, self.project.id, key)
            if row is not None and key not in labels:
                labels[key] = PasteLabel(kind=row.kind, title=row.title)
        return PasteResult(
            project=self.project.key_prefix,
            outcomes=tuple(outcomes),
            refs={name: row.key for name, row in self.refs.items()},
            items=tuple(items),
            decisions=tuple(decisions),
            completed=report.completed,
            reopened=report.reopened,
            blocked=report.blocked,
            labels=labels,
        )

    def _own_key(self, value: str) -> str:
        """Drop a qualifier naming the block's project; refuse any other."""
        parts = split_qualified(value)
        if parts is not None and parts[0] not in (None, self.project.key_prefix):
            raise QualifierError(CONFLICT)
        return unqualified(value)
