"""Raised when a goal or batch is set done by hand while work under it is open."""

from collections.abc import Sequence

from xoot.exceptions.rule_violation_error import RuleViolationError

# More keys than this are summarized as "and N more".
KEYS_SHOWN = 10


class OpenChildrenError(RuleViolationError):
    """
    A goal or batch cannot be moved to a done state while any child work item
    or backlog item on it is still open; it completes on its own once they
    close. Nothing was written.

    The message is fixed text plus stored keys only, so it is safe to show.
    """

    def __init__(self, key: str, open_keys: Sequence[str]) -> None:
        """
        Record the item and what holds it open.

        Args:
            - key (str): the goal or batch.
            - open_keys (Sequence[str]): every open child and backlog key.
        """
        shown = ", ".join(open_keys[:KEYS_SHOWN])
        more = len(open_keys) - KEYS_SHOWN
        suffix = f" and {more} more" if more > 0 else ""
        super().__init__(
            f"{key} still has open work: {shown}{suffix}; it completes on its "
            "own once they are done or dropped"
        )
        self.key = key
        self.open_keys = tuple(open_keys)
