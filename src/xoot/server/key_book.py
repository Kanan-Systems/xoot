"""Id-to-key and state-to-category lookups for one tool call."""

import sqlite3

from xoot.models.item.item import Item
from xoot.models.workflow.category import Category
from xoot.models.workflow.workflow_definition import WorkflowDefinition
from xoot.repositories.decision import decision_db
from xoot.repositories.item import item_db
from xoot.repositories.session import session_db
from xoot.services.lookups import active_workflow, require_project
from xoot.utils.utils import session_key


class KeyBook:
    """
    Turns stored ids into public keys, and item states into categories,
    within one open transaction.

    Answers are cached for the life of the book, which is one tool call, so
    rendering a long list costs one query per distinct reference. A missing
    reference renders as None rather than failing the whole call.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """
        Start an empty book.

        Args:
            - conn (sqlite3.Connection): a connection inside a transaction.
        """
        self.conn = conn
        self._items: dict[int, str | None] = {}
        self._sessions: dict[int, str | None] = {}
        self._decisions: dict[int, str | None] = {}
        self._prefixes: dict[int, str] = {}
        self._workflows: dict[int, WorkflowDefinition] = {}

    def item_key(self, item_id: int | None) -> str | None:
        """
        Return an item's key.

        Args:
            - item_id (int | None): the item id.

        Returns:
            - key (str | None): the key, or None for None or a missing item.
        """
        if item_id is None:
            return None
        if item_id not in self._items:
            item = item_db.get(self.conn, item_id)
            self._items[item_id] = None if item is None else item.key
        return self._items[item_id]

    def session_key(self, session_id: int | None) -> str | None:
        """
        Return a session's key.

        Args:
            - session_id (int | None): the session id.

        Returns:
            - key (str | None): the key, or None for None or a missing session.
        """
        if session_id is None:
            return None
        if session_id not in self._sessions:
            session = session_db.get(self.conn, session_id)
            self._sessions[session_id] = (
                None
                if session is None
                else session_key(self.prefix(session.project_id), session.number)
            )
        return self._sessions[session_id]

    def decision_key(self, decision_id: int | None) -> str | None:
        """
        Return a decision's key.

        Args:
            - decision_id (int | None): the decision id.

        Returns:
            - key (str | None): the key, or None for None or a missing decision.
        """
        if decision_id is None:
            return None
        if decision_id not in self._decisions:
            decision = decision_db.get(self.conn, decision_id)
            self._decisions[decision_id] = None if decision is None else decision.key
        return self._decisions[decision_id]

    def prefix(self, project_id: int) -> str:
        """
        Return a project's key prefix.

        Args:
            - project_id (int): the project id.

        Returns:
            - prefix (str): the key prefix.

        Raises:
            - NotFoundError: no such project.
        """
        if project_id not in self._prefixes:
            self._prefixes[project_id] = require_project(
                self.conn, project_id
            ).key_prefix
        return self._prefixes[project_id]

    def category(self, item: Item, state: str | None = None) -> Category | None:
        """
        Return the category of an item's state in its project's workflow.

        Args:
            - item (Item): the item.
            - state (str | None): another state of the same item's kind to
              classify; the item's own state when None.

        Returns:
            - category (Category | None): the category, or None for a state
              the workflow does not know.

        Raises:
            - NotFoundError: the project or its workflow is missing.
        """
        if item.project_id not in self._workflows:
            project = require_project(self.conn, item.project_id)
            self._workflows[item.project_id] = active_workflow(
                self.conn, project
            ).definition
        workflow = self._workflows[item.project_id].for_kind(item.kind)
        return workflow.category_of(item.state if state is None else state)
