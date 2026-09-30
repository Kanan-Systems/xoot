"""Raised when a move, push or drop would touch too many items at once."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class PlanSizeError(RuleViolationError):
    """
    The plan is larger than the per-call cap. Nothing was written.

    The message is fixed text plus a stored key and counts, so it is safe to
    show.
    """

    def __init__(self, key: str, size: int, cap: int) -> None:
        """
        Record the plan's root and size.

        Args:
            - key (str): the plan's root item.
            - size (int): how many items the plan would change.
            - cap (int): the most one plan may change.
        """
        super().__init__(
            f"the plan for {key} changes {size} items; at most {cap} per move, "
            "push or drop"
        )
        self.key = key
        self.size = size
        self.cap = cap
