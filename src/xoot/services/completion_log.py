"""
What the completion engine did inside one write transaction, and which
items the transaction wrote.

The log is shared by a write scope and its system-actor copies, so every
completion and reopening in the transaction lands in one report. The last
outcome per key wins: a batch reopened after completing in the same write
is reported as reopened. Written items are kept by id, since a move changes
their keys.
"""

from typing import Literal

from xoot.models.item.blocked_item import BlockedItem
from xoot.models.item.completion_report import CompletionReport

type Outcome = Literal["completed", "reopened"]


class CompletionLog:
    """
    Ordered outcomes per key and the ids of written items, turned into a
    CompletionReport on demand.
    """

    def __init__(self) -> None:
        """Start an empty log."""
        self._outcomes: dict[str, Outcome] = {}
        self._blocked: dict[str, int] = {}
        # A dict as an ordered set: first-write order.
        self._written: dict[int, None] = {}

    def wrote(self, item_id: int) -> None:
        """
        Note that the transaction created or changed an item.

        Args:
            - item_id (int): the item's row id.
        """
        self._written[item_id] = None

    def written(self) -> tuple[int, ...]:
        """
        List the items the transaction wrote.

        Returns:
            - ids (tuple[int, ...]): row ids, in first-write order.
        """
        return tuple(self._written)

    def record(self, key: str, outcome: Outcome) -> None:
        """
        Note that the engine completed or reopened an item.

        Args:
            - key (str): the item key.
            - outcome (Outcome): completed or reopened.
        """
        self._outcomes.pop(key, None)
        self._outcomes[key] = outcome
        self._blocked.pop(key, None)

    def block(self, key: str, open_backlog: int) -> None:
        """
        Note that an item stays open only because of its open backlog.

        Args:
            - key (str): the goal or batch key.
            - open_backlog (int): how many open backlog items sit on it.
        """
        self._blocked[key] = open_backlog

    def unblock(self, key: str) -> None:
        """
        Forget a block: the item now has open work of its own.

        Args:
            - key (str): the goal or batch key.
        """
        self._blocked.pop(key, None)

    def report(self) -> CompletionReport:
        """
        Summarize the log.

        Returns:
            - report (CompletionReport): completed, reopened and blocked keys;
              changed is left for the scope, which can read the rows back.
        """
        return CompletionReport(
            completed=tuple(k for k, v in self._outcomes.items() if v == "completed"),
            reopened=tuple(k for k, v in self._outcomes.items() if v == "reopened"),
            blocked=tuple(
                BlockedItem(key=key, open_backlog=count)
                for key, count in self._blocked.items()
            ),
        )
