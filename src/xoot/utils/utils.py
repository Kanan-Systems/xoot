"""
Helpers used by more than one module.

canonical_sha256 is the one way xoot hashes structured data, so the argument
digest and the plan digest of a two-phase call can never drift apart;
body_digest is the one way it hashes a body, so a plan entry and a create
event pin the same text identically.
session_key lives here because sessions, unlike items and decisions, store
no key, and both the services and the server need to build one.
"""

import hashlib
import json
from typing import Any


def canonical_sha256(value: Any) -> str:
    """
    Hash JSON-ready data canonically.

    Sorted keys, no whitespace and ASCII escapes give one byte string per
    value, whatever order or spacing produced it.

    Args:
        - value (Any): JSON-ready data.

    Returns:
        - digest (str): lowercase hex SHA-256.
    """
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def body_digest(body: str) -> str:
    """
    Digest an item or decision body, so a record pins it without carrying it.

    Args:
        - body (str): the body text.

    Returns:
        - digest (str): lowercase hex SHA-256 of its UTF-8 bytes.
    """
    return hashlib.sha256(body.encode()).hexdigest()


def session_key(prefix: str, number: int) -> str:
    """
    Build a session's public key.

    Args:
        - prefix (str): the project's key prefix.
        - number (int): the per-project session number.

    Returns:
        - key (str): e.g. "xoot-S3".
    """
    return f"{prefix}-S{number}"
