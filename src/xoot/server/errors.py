"""
Safe tool errors.

Every message is a class name plus a fixed reason, built from structured
fields only: never str() of a driver error, never SQL, never an input value.
A validation error reports field locations and pydantic error types; location
parts that are not known field names (dict keys, unknown extra fields) are
masked, since those come from the caller.
"""

from pydantic import BaseModel, ValidationError

from xoot.exceptions.backlog_error import BacklogError
from xoot.exceptions.confirm_token_error import ConfirmTokenError
from xoot.exceptions.cross_project_error import CrossProjectError
from xoot.exceptions.decision_error import DecisionError
from xoot.exceptions.duplicate_error import DuplicateError
from xoot.exceptions.hierarchy_error import HierarchyError
from xoot.exceptions.invalid_id_error import InvalidIdError
from xoot.exceptions.legacy_database_error import LegacyDatabaseError
from xoot.exceptions.not_found_error import NotFoundError
from xoot.exceptions.qualifier_error import QualifierError
from xoot.exceptions.schema_version_error import SchemaVersionError
from xoot.exceptions.stale_write_error import StaleWriteError
from xoot.exceptions.state_error import StateError
from xoot.exceptions.store_error import StoreError
from xoot.exceptions.unsafe_path_error import UnsafePathError
from xoot.exceptions.version_conflict_error import VersionConflictError
from xoot.exceptions.xoot_error import XootError
from xoot.models.confirm.confirmation import Confirmation
from xoot.models.decision.decision_changes_input import DecisionChangesInput
from xoot.models.decision.decision_create import DecisionCreate
from xoot.models.decision.decision_update import DecisionUpdate
from xoot.models.item.bulk_create import BulkCreate
from xoot.models.item.bulk_item import BulkItem
from xoot.models.item.item_changes_input import ItemChangesInput
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_update import ItemUpdate
from xoot.models.item.tree_query import TreeQuery
from xoot.server.schemas.bulk_item_input import BulkItemInput
from xoot.utils.keys import is_key

# Every tool argument name; a test keeps this in step with the registered tools.
TOOL_ARGUMENTS = frozenset(
    {
        "at", "batch", "body", "changes", "confirm_token", "depth",
        "expected_version", "found_on", "include_closed", "include_done",
        "items", "key", "kind", "limit", "owner", "parent", "project", "root",
        "status", "supersedes", "title",
    }
)  # fmt: skip

_VALIDATED_MODELS: tuple[type[BaseModel], ...] = (
    BulkCreate, BulkItem, BulkItemInput, Confirmation, DecisionChangesInput,
    DecisionCreate, DecisionUpdate, ItemChangesInput, ItemCreate, ItemDraft,
    ItemUpdate, TreeQuery,
)  # fmt: skip

KNOWN_FIELDS = TOOL_ARGUMENTS | frozenset(
    name for model in _VALIDATED_MODELS for name in model.model_fields
)

# Stored reference columns and the public names tools use for them.
PUBLIC_NAMES = {
    "parent_id": "parent",
    "awaiting_decision_id": "awaiting_decision",
    "owner_item_id": "owner",
    "supersedes_id": "supersedes",
    "found_on_item_id": "found_on",
    "covered_by_item_id": "covered_by",
    "origin_item_id": "origin",
    "item_id": "item",
}

_REASONS: dict[type[XootError], str] = {
    CrossProjectError: "a referenced item or decision belongs to another project",
    HierarchyError: (
        "the parent breaks the hierarchy: a goal sits on the project, a batch "
        "in a goal, a subtask in a batch; backlog items come from capture"
    ),
    StateError: "the state is not in the workflow, or the transition is not allowed",
    DuplicateError: "the value is already registered",
    NotFoundError: "a referenced record does not exist",
    InvalidIdError: "an id or version is not a valid integer",
    StaleWriteError: "a record changed during the write; retry",
    UnsafePathError: "the database path failed the ownership and permission checks",
    SchemaVersionError: "the database was written by a newer xoot",
}
# Errors whose messages are fixed text plus stored keys or prefixes only.
_DETAILED: tuple[type[XootError], ...] = (
    BacklogError, ConfirmTokenError, DecisionError, LegacyDatabaseError,
    QualifierError,
)  # fmt: skip


def not_found_message(key: str) -> str:
    """
    Build the message for a key that resolves to nothing.

    A well-formed key is echoed (it can only hold [a-z0-9/:-]); any other
    text is not, since it is arbitrary caller input.

    Args:
        - key (str): the key as the caller sent it.

    Returns:
        - message (str): "not found: <key>".
    """
    return f"not found: {key if is_key(key) else 'malformed key'}"


def safe_message(exc: XootError | ValidationError) -> str:
    """
    Describe a domain or validation error without leaking its details.

    Args:
        - exc (XootError | ValidationError): the error to describe.

    Returns:
        - message (str): "<ClassName>: <reason>".
    """
    if isinstance(exc, ValidationError):
        return f"ValidationError: invalid arguments: {_locations(exc)}"
    if isinstance(exc, VersionConflictError):
        return _conflict_message(exc)
    name = type(exc).__name__
    if isinstance(exc, _DETAILED):
        # Written by the services from fixed text and stored keys; never input.
        return f"{name}: {exc}"
    for cls in type(exc).__mro__:
        if cls in _REASONS:
            return f"{name}: {_REASONS[cls]}"
    if isinstance(exc, StoreError):
        code = getattr(exc, "sqlite_errorname", None)
        suffix = f" ({code})" if code else ""
        return f"{name}: the database could not complete the operation{suffix}"
    return f"{name}: the request was refused"


def _conflict_message(exc: VersionConflictError) -> str:
    fields = ", ".join(PUBLIC_NAMES.get(f, f) for f in exc.changed_fields)
    actors = ", ".join(f"{a.kind}/{a.client}" for a in exc.actors)
    return (
        f"VersionConflictError: {exc.key} is at version {exc.current_version}; "
        f"changed since your version: {fields or 'nothing recorded'}; "
        f"by: {actors or 'unknown'}"
    )


def _locations(exc: ValidationError) -> str:
    rendered = set()
    for error in exc.errors():
        parts = [
            part if isinstance(part, str) and part in KNOWN_FIELDS else "*"
            for part in error["loc"]
        ]
        rendered.add(f"{'.'.join(parts) or '*'} ({error['type']})")
    return ", ".join(sorted(rendered))
