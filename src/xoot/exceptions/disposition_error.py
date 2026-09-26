"""Raised when a session close has missing or unexpected dispositions."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class DispositionError(RuleViolationError):
    """Dispositions do not match the session's open linked items."""

    def __init__(self, message: str, item_ids: tuple[int, ...]) -> None:
        """
        Record which items are at fault.

        Args:
            - message (str): what is wrong with the dispositions.
            - item_ids (tuple[int, ...]): the items concerned, sorted.
        """
        super().__init__(f"{message}: {', '.join(map(str, item_ids))}")
        self.item_ids = item_ids
