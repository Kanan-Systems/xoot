"""
Public key grammar: projects <prefix>, items <prefix>-<n>, decisions
<prefix>-D<n>, sessions <prefix>-S<n>.

Key prefixes are lowercase, so the uppercase D and S cannot be mistaken for
part of a prefix. Parsing is strict: anything that does not match, or whose
number does not fit a stored id, is not a key.
"""

import re

from xoot.models.fields import SQLITE_INT_MAX

_PREFIX = r"[a-z][a-z0-9-]{1,31}"
_NUMBER = r"[1-9][0-9]{0,18}"

PREFIX_KEY = re.compile(rf"^{_PREFIX}$")
ITEM_KEY = re.compile(rf"^({_PREFIX})-({_NUMBER})$")
DECISION_KEY = re.compile(rf"^({_PREFIX})-D({_NUMBER})$")
SESSION_KEY = re.compile(rf"^({_PREFIX})-S({_NUMBER})$")


def parse_key(pattern: re.Pattern[str], text: str) -> tuple[str, int] | None:
    """
    Split a key into its project prefix and number.

    Args:
        - pattern (re.Pattern[str]): ITEM_KEY, DECISION_KEY or SESSION_KEY.
        - text (str): the candidate key.

    Returns:
        - parts (tuple[str, int] | None): (prefix, number), or None when the
          text is not a key of that kind.
    """
    match = pattern.fullmatch(text)
    if match is None:
        return None
    number = int(match.group(2))
    if number > SQLITE_INT_MAX:
        return None
    return match.group(1), number


def is_key(text: str) -> bool:
    """
    Tell whether a string is a well-formed key of any kind.

    Args:
        - text (str): the candidate key.

    Returns:
        - well_formed (bool): True for an item, decision or session key.
    """
    return any(
        parse_key(pattern, text) is not None
        for pattern in (ITEM_KEY, DECISION_KEY, SESSION_KEY)
    )
