"""
Workflow definitions as TOML files, using only the standard library.

The writer emits exactly one structure, per item kind:

    [kinds.<kind>]
    [[kinds.<kind>.states]]     name = "...", category = "..."
    [kinds.<kind>.defaults]     <category> = "<state>"
    [kinds.<kind>.transitions]  <state> = ["<state>", ...]   (only if restricted)

An empty transitions table means "restricted, nothing allowed"; a missing one
means unrestricted, so the two stay distinct across a round trip. The reader
parses with tomllib and validates with WorkflowDefinition, which rejects any
key outside that structure. A file from xoot 0.2, which still uses the
removed "backlogged" category, is refused with a message that says so.
"""

import os
import re
import stat
import tomllib
from pathlib import Path

from xoot.exceptions.workflow_file_error import WorkflowFileError
from xoot.models.item.item_kind import ItemKind
from xoot.models.workflow.workflow_definition import WorkflowDefinition

MAX_BYTES = 64 * 1024
LEGACY_CATEGORY = "backlogged"
BACKLOGGED_REMOVED = (
    'the workflow file uses the "backlogged" category from xoot 0.2; it was '
    "removed in 0.3, where backlog is an item kind: drop those states and the "
    "backlogged default, add done defaults, and give the backlog kind a "
    "workflow (export the current one for an example)"
)

_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")
_ESCAPES = {
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
    '"': '\\"',
    "\\": "\\\\",
}


def dump_workflow(definition: WorkflowDefinition) -> str:
    """
    Render a workflow definition as TOML.

    Args:
        - definition (WorkflowDefinition): the definition.

    Returns:
        - text (str): the TOML document, kinds in their fixed order.
    """
    lines: list[str] = []
    for kind in ItemKind:
        workflow = definition.for_kind(kind)
        table = f"kinds.{_key(kind)}"
        lines += [f"[{table}]", ""]
        for spec in workflow.states:
            lines += [
                f"[[{table}.states]]",
                f"name = {basic_string(spec.name)}",
                f"category = {basic_string(spec.category)}",
                "",
            ]
        lines.append(f"[{table}.defaults]")
        lines += [
            f"{_key(c)} = {basic_string(s)}" for c, s in workflow.defaults.items()
        ]
        lines.append("")
        if workflow.transitions is not None:
            lines.append(f"[{table}.transitions]")
            for source, targets in workflow.transitions.items():
                values = ", ".join(basic_string(target) for target in targets)
                lines.append(f"{_key(source)} = [{values}]")
            lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def load_workflow(data: bytes) -> WorkflowDefinition:
    """
    Parse and validate a TOML workflow definition.

    Args:
        - data (bytes): the file's contents.

    Returns:
        - definition (WorkflowDefinition): the validated definition.

    Raises:
        - WorkflowFileError: the data is over MAX_BYTES, not UTF-8 or not
          TOML, or uses the removed "backlogged" category.
        - pydantic.ValidationError: the TOML is not a valid definition.
    """
    if len(data) > MAX_BYTES:
        raise WorkflowFileError(f"the workflow file is larger than {MAX_BYTES} bytes")
    try:
        document = tomllib.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise WorkflowFileError("the workflow file is not valid UTF-8 TOML") from exc
    if _names_backlogged(document):
        raise WorkflowFileError(BACKLOGGED_REMOVED)
    return WorkflowDefinition.model_validate(document)


def _names_backlogged(document: dict[str, object]) -> bool:
    """Whether a 0.2 file uses the removed category, as a state or a default."""
    kinds = document.get("kinds")
    if not isinstance(kinds, dict):
        return False
    for table in kinds.values():
        if not isinstance(table, dict):
            continue
        states = table.get("states")
        if isinstance(states, list) and any(
            isinstance(s, dict) and s.get("category") == LEGACY_CATEGORY for s in states
        ):
            return True
        defaults = table.get("defaults")
        if isinstance(defaults, dict) and LEGACY_CATEGORY in defaults:
            return True
    return False


def read_workflow_file(path: Path) -> WorkflowDefinition:
    """
    Read a workflow file, refusing anything but a regular file within the limit.

    At most MAX_BYTES + 1 bytes are read, so a huge file or a device is
    refused without being read in full.

    Args:
        - path (Path): the file.

    Returns:
        - definition (WorkflowDefinition): the validated definition.

    Raises:
        - WorkflowFileError: the file cannot be opened, is not a regular
          file, or is too large, not UTF-8 or not TOML.
        - pydantic.ValidationError: the TOML is not a valid definition.
    """
    try:
        with path.open("rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise WorkflowFileError("the workflow path is not a regular file")
            data = handle.read(MAX_BYTES + 1)
    except OSError as exc:
        raise WorkflowFileError("the workflow file could not be read") from exc
    return load_workflow(data)


def _key(name: str) -> str:
    """A bare key when the name allows one, else a quoted key."""
    return name if _BARE_KEY.fullmatch(name) else basic_string(name)


def basic_string(value: str) -> str:
    """
    Quote a value as a TOML basic string.

    Validated state and category names never need escaping, but the writer
    does not rely on that: quotes, backslashes and control characters are
    always escaped.

    Args:
        - value (str): the value.

    Returns:
        - text (str): the quoted, escaped string.
    """
    escaped = []
    for char in value:
        if char in _ESCAPES:
            escaped.append(_ESCAPES[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            escaped.append(f"\\u{ord(char):04X}")
        else:
            escaped.append(char)
    return '"' + "".join(escaped) + '"'
