"""
Binding two-phase tool calls to their arguments.

The preview and the apply hash the same canonical JSON of the tool's
arguments, without the token, so a token only applies the exact call that
was previewed.
"""

from collections.abc import Mapping
from typing import Any

from xoot.models.confirm.confirmation import Confirmation
from xoot.utils.utils import canonical_sha256


def args_digest(arguments: Mapping[str, Any]) -> str:
    """
    Hash a call's arguments canonically.

    One digest per argument set, whatever order or spacing the client used.

    Args:
        - arguments (Mapping[str, Any]): JSON-ready arguments, token excluded.

    Returns:
        - digest (str): lowercase hex SHA-256.
    """
    return canonical_sha256(dict(arguments))


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
