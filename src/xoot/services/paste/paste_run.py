"""
The state of one block's execution inside its write transaction.

Every op writes through the run's single WriteScope, so the whole block
shares one timestamp and commits or rolls back as one. The actor is Claude
and the client is paste, also when the block writes into a session another
client started. Keys resolve through the connection-based key resolvers;
refs resolve to the current row of the record the block created.
"""

import sqlite3
from typing import Literal

from xoot.exceptions.not_found_error import NotFoundError
from xoot.exceptions.paste_error import PasteError
from xoot.models.decision.decision import Decision
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.session.client import Client
from xoot.models.session.session import Session
from xoot.models.session.session_status import SessionStatus
from xoot.repositories.decision import decision_db
from xoot.repositories.item import item_db
from xoot.services import key_resolver
from xoot.services.lookups import require_decision, require_item
from xoot.services.paste.models.fields import is_ref, ref_name
from xoot.services.paste.models.paste_auto_backlog import PasteAutoBacklog
from xoot.services.paste.models.paste_block import PasteBlock
from xoot.services.paste.models.paste_decision_state import PasteDecisionState
from xoot.services.paste.models.paste_item_state import PasteItemState
from xoot.services.paste.models.paste_label import PasteLabel
from xoot.services.paste.models.paste_op_outcome import PasteOpOutcome
from xoot.services.paste.models.paste_result import PasteResult
from xoot.services.paste.rules import NO_SESSION
from xoot.services.project_resolver import by_name, known_names
from xoot.services.write_scope import WriteScope
from xoot.utils.utils import session_key

PASTE_ACTOR = Actor(kind=ActorKind.CLAUDE, client=Client.PASTE)

type Touched = tuple[Literal["item", "decision"], int]


class PasteRun:
    """
    One execution of a block: the scope every op writes through, the refs
    defined so far, the auto-backlog side effects, and every item and
    decision the block touched, in first-touch order.
    """

    def __init__(self, conn: sqlite3.Connection, block: PasteBlock) -> None:
        """
        Resolve the block's project and, if named, join its open session.

        Args:
            - conn (sqlite3.Connection): a connection inside a write transaction.
            - block (PasteBlock): the checked block.

        Raises:
            - PasteError: the project is unknown, or the named session is
              missing, closed or in another project.
        """
        self.conn = conn
        found = by_name(conn, block.project)
        if found is None:
            names = ", ".join(known_names(conn)) or "none registered"
            raise PasteError(f"project not resolved; known names: {names}")
        self.project = found[0]
        self.scope = WriteScope(conn, WriteContext(actor=PASTE_ACTOR))
        self.session: Session | None = None
        self.refs: dict[str, Item | Decision] = {}
        self.auto_backlog: list[PasteAutoBacklog] = []
        # A dict as an ordered set: the result lists records in touch order.
        self._touched: dict[Touched, None] = {}
        if block.session is not None:
            self._join(block.session)

    def attach(self, session: Session) -> None:
        """
        Make a session the block's session; later writes are attributed to it.

        Args:
            - session (Session): the open session.
        """
        self.session = session
        self.scope = self.scope.with_session(session.id)

    def open_session(self) -> Session:
        """
        Return the block's session.

        Returns:
            - session (Session): the session named or started by the block.

        Raises:
            - PasteError: no session yet (check_block rules this out).
        """
        if self.session is None:
            raise PasteError(NO_SESSION)
        return self.session

    def session_key(self, session: Session) -> str:
        """
        Build the public key of a session of this project.

        Args:
            - session (Session): the session.

        Returns:
            - key (str): e.g. "xoot-S3".
        """
        return session_key(self.project.key_prefix, session.number)

    def touch(self, row: Item | Decision) -> None:
        """
        Remember a record the block wrote or disposed.

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
            - value (str): a key, or "$<ref>" of an item this block created.

        Returns:
            - item (Item): the current row.

        Raises:
            - NotFoundError: the key names no item, or the ref no item.
        """
        if not is_ref(value):
            return key_resolver.item_by_key(self.conn, value)
        row = self.refs.get(ref_name(value) or "")
        if not isinstance(row, Item):
            raise NotFoundError("item ref", key_resolver.MALFORMED)
        return require_item(self.conn, row.id)

    def decision(self, value: str) -> Decision:
        """
        Resolve a decision key or ref to its current row.

        Args:
            - value (str): a key, or "$<ref>" of a decision this block created.

        Returns:
            - decision (Decision): the current row.

        Raises:
            - NotFoundError: the key names no decision, or the ref none.
        """
        if not is_ref(value):
            return key_resolver.decision_by_key(self.conn, value)
        row = self.refs.get(ref_name(value) or "")
        if not isinstance(row, Decision):
            raise NotFoundError("decision ref", key_resolver.MALFORMED)
        return require_decision(self.conn, row.id)

    def item_keys(self, item_ids: tuple[int, ...]) -> str:
        """
        List item keys for a message.

        Args:
            - item_ids (tuple[int, ...]): item ids.

        Returns:
            - keys (str): the keys, comma-separated.
        """
        return ", ".join(require_item(self.conn, item_id).key for item_id in item_ids)

    def result(self, outcomes: list[PasteOpOutcome]) -> PasteResult:
        """
        Read back every touched record and summarize the run.

        Args:
            - outcomes (list[PasteOpOutcome]): every op's outcome, in order.

        Returns:
            - result (PasteResult): the outcomes, refs, final records, side
              effects, and the labels the plan shows.
        """
        session = self.open_session()
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
        return PasteResult(
            project=self.project.key_prefix,
            session=self.session_key(session),
            session_status=session.status,
            outcomes=tuple(outcomes),
            refs={name: row.key for name, row in self.refs.items()},
            items=tuple(items),
            decisions=tuple(decisions),
            auto_backlog=tuple(self.auto_backlog),
            labels=labels,
        )

    def _join(self, key: str) -> None:
        try:
            session = key_resolver.session_by_key(self.conn, key)
        except NotFoundError as exc:
            ref = key_resolver.safe_ref(key)
            raise PasteError(f"session not found: {ref}") from exc
        if session.project_id != self.project.id:
            raise PasteError(f"session {key} belongs to another project")
        if session.status is not SessionStatus.OPEN:
            raise PasteError(f"session {key} is not open")
        self.attach(session)
