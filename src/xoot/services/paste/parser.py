"""
Turning pasted text into a validated block.

The text is decoded as strict UTF-8 within a size cap, the one fenced block
whose info string is exactly "xoot" is cut out (any other text, including a
xoot-receipt block, is ignored), and its JSON is parsed only by Pydantic's
depth-limited model_validate_json. Fences are tracked the CommonMark way, so
an example block nested in a longer fence is content, not a block.

A validation error is described by op number, field names and Pydantic error
types only: its messages and dict keys can quote the input.
"""

import re

from pydantic import BaseModel, ValidationError

from xoot.exceptions.paste_error import PasteError
from xoot.models.decision.decision_changes_input import DecisionChangesInput
from xoot.models.item.item_changes_input import ItemChangesInput
from xoot.services.paste.models.backlog_cover_op import BacklogCoverOp
from xoot.services.paste.models.backlog_push_op import BacklogPushOp
from xoot.services.paste.models.capture_op import CaptureOp
from xoot.services.paste.models.decision_record_op import DecisionRecordOp
from xoot.services.paste.models.decision_update_op import DecisionUpdateOp
from xoot.services.paste.models.item_create_op import ItemCreateOp
from xoot.services.paste.models.item_update_op import ItemUpdateOp
from xoot.services.paste.models.paste_block import OP_NAMES, PasteBlock
from xoot.services.paste.rules import check_block

MAX_BYTES = 256 * 1024
INFO_STRING = "xoot"
NO_BLOCK = "no xoot block found"
MANY_BLOCKS = "more than one xoot block; send one"
UNCLOSED = "the xoot block is not closed"
# Errors past this many are summarized, so a hostile block cannot flood stderr.
ERRORS_SHOWN = 10
_UTF8_BOM = "﻿"
# Up to three spaces of indent, then a run of backticks or tildes (CommonMark).
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_MODELS: tuple[type[BaseModel], ...] = (
    PasteBlock, ItemCreateOp, ItemUpdateOp, CaptureOp, BacklogCoverOp,
    BacklogPushOp, DecisionRecordOp, DecisionUpdateOp, ItemChangesInput,
    DecisionChangesInput,
)  # fmt: skip
_FIELD_NAMES = frozenset(name for model in _MODELS for name in model.model_fields)


def decode_paste(data: bytes) -> str:
    """
    Decode pasted bytes, refusing anything over the cap or not UTF-8.

    The caller reads at most MAX_BYTES + 1 bytes, so one byte over the cap
    is enough to tell. A leading byte-order mark is dropped.

    Args:
        - data (bytes): the bytes read.

    Returns:
        - text (str): the decoded text.

    Raises:
        - PasteError: the input is over MAX_BYTES or not valid UTF-8.
    """
    if len(data) > MAX_BYTES:
        raise PasteError(f"the paste is larger than {MAX_BYTES // 1024} KiB")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PasteError("the paste is not valid UTF-8") from exc
    return text.removeprefix(_UTF8_BOM)


def parse_paste(text: str) -> PasteBlock:
    """
    Extract, parse and check the one xoot block in a paste.

    Args:
        - text (str): the whole pasted text.

    Returns:
        - block (PasteBlock): the validated block.

    Raises:
        - PasteError: no block, more than one, an unclosed one, invalid JSON
          or fields (a key off the grammar included), or a broken ref or
          version rule.
    """
    body = extract_block(text)
    try:
        block = PasteBlock.model_validate_json(body)
    except ValidationError as exc:
        raise PasteError(f"invalid xoot block: {describe_errors(exc)}") from exc
    check_block(block)
    return block


def extract_block(text: str) -> str:
    """
    Return the body of the one fenced block whose info string is "xoot".

    Args:
        - text (str): the whole pasted text.

    Returns:
        - body (str): the lines between the fences.

    Raises:
        - PasteError: zero blocks, more than one, or one left unclosed.
    """
    bodies: list[str] = []
    fence: str | None = None
    body: list[str] | None = None
    for raw in text.split("\n"):
        line = raw.rstrip("\r")
        if fence is None:
            match = _FENCE.match(line)
            if match is None:
                continue
            marker, info = match.group(1), match.group(2).strip()
            # A backtick fence's info string cannot hold a backtick.
            if marker.startswith("`") and "`" in info:
                continue
            fence = marker
            body = [] if marker == "```" and info == INFO_STRING else None
        elif _closes(line, fence):
            if body is not None:
                bodies.append("\n".join(body))
            fence, body = None, None
        elif body is not None:
            body.append(line)
    if body is not None:
        raise PasteError(UNCLOSED)
    if not bodies:
        raise PasteError(NO_BLOCK)
    if len(bodies) > 1:
        raise PasteError(MANY_BLOCKS)
    return bodies[0]


def describe_errors(exc: ValidationError) -> str:
    """
    Describe a block's validation errors without quoting the input.

    Args:
        - exc (ValidationError): the error from PasteBlock.

    Returns:
        - text (str): "; "-separated "<where>: <field> (<type>)" entries.
    """
    entries = sorted({_describe(error["loc"], error["type"]) for error in exc.errors()})
    if len(entries) > ERRORS_SHOWN:
        extra = len(entries) - ERRORS_SHOWN
        entries = [*entries[:ERRORS_SHOWN], f"and {extra} more"]
    return "; ".join(entries)


def _closes(line: str, fence: str) -> bool:
    """A closing fence: the same character, at least as long, nothing after."""
    stripped = line.strip()
    return (
        len(stripped) >= len(fence)
        and set(stripped) == {fence[0]}
        and len(line) - len(line.lstrip(" ")) <= 3
    )


def _describe(loc: tuple[int | str, ...], error_type: str) -> str:
    """One error: its op, the known field names on its path, and its type."""
    if error_type == "json_invalid":
        return "the block is not valid JSON (json_invalid)"
    where = "block"
    parts = list(loc)
    if len(parts) >= 2 and parts[0] == "ops" and isinstance(parts[1], int):
        where = f"op {parts[1] + 1}"
        parts = parts[2:]
        if parts and parts[0] in OP_NAMES:
            where = f"{where} ({parts[0]})"
            parts = parts[1:]
    fields = ".".join(_safe_part(part) for part in parts) or "*"
    return f"{where}: {fields} ({error_type})"


def _safe_part(part: int | str) -> str:
    """List indexes and known field names are safe; dict keys are input."""
    if isinstance(part, int):
        return str(part)
    return part if part in _FIELD_NAMES else "*"
