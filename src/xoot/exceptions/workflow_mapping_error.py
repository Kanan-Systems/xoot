"""Raised when a workflow change would strand items in removed states."""

from xoot.exceptions.rule_violation_error import RuleViolationError


class WorkflowMappingError(RuleViolationError):
    """The state mapping is missing, or names states it may not remap."""
