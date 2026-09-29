"""Raised when an item's parent breaks the goal > batch > subtask hierarchy."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class HierarchyError(RuleViolationError):
    """
    The parent kind is not allowed for the child kind: goals sit on the
    project, batches in a goal, subtasks in a batch, and backlog items in a
    batch, a goal or on the project.
    """
