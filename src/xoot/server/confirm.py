"""
Binding two-phase tool calls to their arguments.

The preview and the apply hash the same canonical JSON of the tool's
arguments, without the token, so a token only applies the exact call that
was previewed.
"""

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from xoot.models.confirm.confirmation import Confirmation


def args_digest(arguments: Mapping[str, Any]) -> str:
    """
    Hash a call's arguments canonically.

    Sorted keys, no whitespace and ASCII escapes give one byte string per
    argument set, whatever order or spacing the client used.

    Args:
        - arguments (Mapping[str, Any]): JSON-ready arguments, token excluded.

    Returns:
        - digest (str): lowercase hex SHA-256.
    """
    canonical = json.dumps(
        arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def confirmation(tool: str, token: str, digest: str) -> Confirmation:
    """
    Build the claim an apply presents to its service.

    Args:
        - tool (str): the tool name.
        - token (str): the confirm_token the caller sent.
        - digest (str): args_digest of this call.

    Returns:
        - confirmation (Confirmation): the claim.
    """
    return Confirmation(token=token, tool=tool, args_sha256=digest)
