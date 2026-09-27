"""
Helpers used by more than one module.

canonical_sha256 is the one way xoot hashes structured data, so the argument
digest and the plan digest of a two-phase call can never drift apart.
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
