"""
The per-transaction write scope: connection, actor context, one timestamp,
and the event recording every mutation must do in the same transaction.
"""

import hashlib
import sqlite3
from datetime import UTC, datetime
from typing import Any, Self

from pydantic import BaseModel

from xoot.models.decision.decision import Decision
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.entity_type import EntityType
from xoot.models.event.event_action import EventAction
from xoot.models.event.new_event import NewEvent
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item import Item
from xoot.models.project.project import Project
from xoot.models.session.session import Session
from xoot.models.workflow.workflow import Workflow
from xoot.repositories.event import event_db

type Tracked = Project | Workflow | Item | Session | Decision

_ENTITY_TYPES: dict[type[BaseModel], EntityType] = {
    Project: EntityType.PROJECT,
    Workflow: EntityType.WORKFLOW,
    Item: EntityType.ITEM,
    Session: EntityType.SESSION,
    Decision: EntityType.DECISION,
}
# updated_at duplicates the event's own created_at, so diffs leave it out.
_NOT_DIFFED = frozenset({"updated_at"})


def changed_fields(
    before: BaseModel, after: BaseModel
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Diff two versions of the same entity as JSON-ready values.

    Args:
        - before (BaseModel): the old version.
        - after (BaseModel): the new version.

    Returns:
        - diff (tuple[dict[str, Any], dict[str, Any]]): old and new values of
          the fields that differ.
    """
    old = before.model_dump(mode="json", exclude=_NOT_DIFFED)
    new = after.model_dump(mode="json", exclude=_NOT_DIFFED)
    changed = [name for name in new if new[name] != old.get(name)]
    return {name: old.get(name) for name in changed}, {
        name: new[name] for name in changed
    }


class WriteScope:
    """
    Everything one write transaction needs, created right after BEGIN.

    All rows written in the scope share one timestamp, and every mutation is
    recorded through it so the event commits or rolls back with the change.
    """

    def __init__(
        self, conn: sqlite3.Connection, ctx: WriteContext, now: datetime | None = None
    ) -> None:
        """
        Start a scope.

        Args:
            - conn (sqlite3.Connection): connection inside a write transaction.
            - ctx (WriteContext): actor and optional session of the write.
            - now (datetime | None): shared timestamp; the current UTC time
              when None.
        """
        self.conn = conn
        self.ctx = ctx
        self.now = datetime.now(UTC) if now is None else now

    def with_session(self, session_id: int) -> Self:
        """
        Return the same scope attributed to a session (e.g. one just started).

        Args:
            - session_id (int): the session id.

        Returns:
            - scope (WriteScope): a scope with the same connection and time.
        """
        ctx = self.ctx.model_copy(update={"session_id": session_id})
        return type(self)(self.conn, ctx, self.now)

    def as_system(self) -> Self:
        """
        Return the same scope attributed to xoot itself.

        For changes xoot derives from the current write (stale backlog
        moves, workflow remaps). The client, session and time stay those of
        the write that triggered them.

        Returns:
            - scope (WriteScope): a scope with a system actor.
        """
        actor = Actor(kind=ActorKind.SYSTEM, client=self.ctx.actor.client)
        ctx = self.ctx.model_copy(update={"actor": actor})
        return type(self)(self.conn, ctx, self.now)

    def created(self, entity: Tracked) -> None:
        """
        Record the creation of an entity with its full snapshot.

        Item and decision bodies are recorded as body_sha256 and body_len
        (characters), not as text: a body can be 32 KB, and the row already
        holds it.

        Args:
            - entity (Tracked): the stored row.
        """
        snapshot = entity.model_dump(mode="json")
        if isinstance(entity, (Item, Decision)):
            body = snapshot.pop("body")
            snapshot["body_sha256"] = hashlib.sha256(body.encode()).hexdigest()
            snapshot["body_len"] = len(body)
        self._append(entity, EventAction.CREATE, None, snapshot)

    def updated(
        self, before: Tracked, after: Tracked, action: EventAction = EventAction.UPDATE
    ) -> bool:
        """
        Record a change to an entity as a diff of the changed fields.

        Args:
            - before (Tracked): the previous row.
            - after (Tracked): the new row.
            - action (EventAction): update, or a more specific action.

        Returns:
            - recorded (bool): False when nothing changed and no event was
              written.
        """
        old, new = changed_fields(before, after)
        if not new:
            return False
        self._append(after, action, old, new)
        return True

    def noted(
        self,
        entity: Tracked,
        action: EventAction,
        after: dict[str, Any],
        before: dict[str, Any] | None = None,
    ) -> None:
        """
        Record a mutation of a row that has no id of its own (alias, path,
        session link) on the entity that owns it.

        Args:
            - entity (Tracked): the owning project or session.
            - action (EventAction): what happened.
            - after (dict[str, Any]): the new values.
            - before (dict[str, Any] | None): the old values, if any.
        """
        self._append(entity, action, before, after)

    def _append(
        self,
        entity: Tracked,
        action: EventAction,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        project_id = entity.id if isinstance(entity, Project) else entity.project_id
        event_db.append(
            self.conn,
            NewEvent(
                project_id=project_id,
                entity_type=_ENTITY_TYPES[type(entity)],
                entity_id=entity.id,
                action=action,
                actor_kind=self.ctx.actor.kind,
                client=self.ctx.actor.client,
                session_id=self.ctx.session_id,
                before=before,
                after=after,
                created_at=self.now,
            ),
        )
