"""
The key grammar: every parser, resolver and pattern in xoot goes through it.

Keys are nested paths of kind-number segments, unique within one project:

    goal-<n>
    goal-<n>/batch-<m>
    goal-<n>/batch-<m>/subtask-<k>
    backlog-<k>                          (project backlog)
    goal-<n>/backlog-<k>                 (goal backlog)
    goal-<n>/batch-<m>/backlog-<k>       (batch backlog)
    <goal, batch or subtask key>/decision-<j>

Any of them may be qualified with a project prefix: <prefix>:<key>. Parsing
is strict: anything that does not match exactly, or whose number does not
fit a stored id, is not a key.
"""

import re

from xoot.models.fields import SQLITE_INT_MAX

PREFIX_PATTERN = r"[a-z][a-z0-9]{1,31}"
_NUMBER = r"[1-9][0-9]{0,18}"
QUALIFIER = ":"
SEPARATOR = "/"
# Long enough for the deepest decision key with 19-digit numbers, qualified.
KEY_MAX = 160

PREFIX_KEY = re.compile(rf"^{PREFIX_PATTERN}$")
_SEGMENT = re.compile(rf"^(goal|batch|subtask|backlog|decision)-({_NUMBER})$")

# The kinds each position of an item key may hold, root first.
_ITEM_SHAPES: tuple[tuple[str, ...], ...] = (
    ("goal",),
    ("goal", "batch"),
    ("goal", "batch", "subtask"),
    ("backlog",),
    ("goal", "backlog"),
    ("goal", "batch", "backlog"),
)
DECISION_OWNER_KINDS = frozenset({"goal", "batch", "subtask"})

type Segments = tuple[tuple[str, int], ...]


def parse_segments(text: str) -> Segments | None:
    """
    Split an unqualified key into its (kind, number) segments.

    Args:
        - text (str): the candidate key, without a prefix.

    Returns:
        - segments (Segments | None): the segments, root first, or None when
          any segment is malformed or a number does not fit a stored id.
    """
    if not text or len(text) > KEY_MAX:
        return None
    segments = []
    for part in text.split(SEPARATOR):
        match = _SEGMENT.fullmatch(part)
        if match is None:
            return None
        number = int(match.group(2))
        if number > SQLITE_INT_MAX:
            return None
        segments.append((match.group(1), number))
    return tuple(segments)


def parse_item_key(text: str) -> Segments | None:
    """
    Parse an unqualified item key.

    Args:
        - text (str): the candidate key.

    Returns:
        - segments (Segments | None): its segments, or None when it is not
          one of the six item shapes.
    """
    segments = parse_segments(text)
    if segments is None:
        return None
    kinds = tuple(kind for kind, _ in segments)
    return segments if kinds in _ITEM_SHAPES else None


def parse_decision_key(text: str) -> tuple[str, int] | None:
    """
    Parse an unqualified decision key into its owner key and number.

    Args:
        - text (str): the candidate key.

    Returns:
        - parts (tuple[str, int] | None): (owner item key, decision number),
          or None when the text is not a decision key on a goal, batch or
          subtask.
    """
    owner, separator, last = text.rpartition(SEPARATOR)
    if not separator:
        return None
    segment = parse_segments(last)
    owner_segments = parse_item_key(owner)
    if segment is None or owner_segments is None or segment[0][0] != "decision":
        return None
    if owner_segments[-1][0] not in DECISION_OWNER_KINDS:
        return None
    return owner, segment[0][1]


def split_qualified(text: str) -> tuple[str | None, str] | None:
    """
    Split an optional project qualifier off a key.

    Args:
        - text (str): "<prefix>:<key>" or "<key>".

    Returns:
        - parts (tuple[str | None, str] | None): (prefix or None, key); None
          when a qualifier is present but is not a well-formed prefix.
    """
    if QUALIFIER not in text:
        return None, text
    prefix, _, key = text.partition(QUALIFIER)
    if PREFIX_KEY.fullmatch(prefix) is None:
        return None
    return prefix, key


def is_item_key(text: str) -> bool:
    """
    Tell whether a string is a well-formed item key, qualified or not.

    Args:
        - text (str): the candidate key.

    Returns:
        - well_formed (bool): True for any of the six item shapes.
    """
    parts = split_qualified(text)
    return parts is not None and parse_item_key(parts[1]) is not None


def is_decision_key(text: str) -> bool:
    """
    Tell whether a string is a well-formed decision key, qualified or not.

    Args:
        - text (str): the candidate key.

    Returns:
        - well_formed (bool): True for <owner key>/decision-<j>.
    """
    parts = split_qualified(text)
    return parts is not None and parse_decision_key(parts[1]) is not None


def is_key(text: str) -> bool:
    """
    Tell whether a string is a well-formed item or decision key.

    Well-formed keys hold only [a-z0-9/:-], so they are safe to echo.

    Args:
        - text (str): the candidate key.

    Returns:
        - well_formed (bool): True for an item or decision key, qualified
          or not.
    """
    return is_item_key(text) or is_decision_key(text)


def child_key(parent_key: str | None, kind: str, number: int) -> str:
    """
    Build the key of an item from its parent's key.

    Args:
        - parent_key (str | None): the parent's key; None on the project.
        - kind (str): the item kind.
        - number (int): the number the parent allocated.

    Returns:
        - key (str): e.g. "goal-1/batch-2".
    """
    segment = f"{kind}-{number}"
    return segment if parent_key is None else f"{parent_key}{SEPARATOR}{segment}"


def decision_key(owner_key: str, number: int) -> str:
    """
    Build a decision's key from its owner's current key.

    Args:
        - owner_key (str): the goal, batch or subtask key.
        - number (int): the number the owner allocated.

    Returns:
        - key (str): e.g. "goal-1/batch-2/decision-3".
    """
    return child_key(owner_key, "decision", number)


def rebase_key(key: str, old_root: str, new_root: str) -> str:
    """
    Move a key from under one root key to under another.

    Args:
        - key (str): the root key itself or a key below it.
        - old_root (str): the root's old key.
        - new_root (str): the root's new key.

    Returns:
        - key (str): the key with its root part replaced.

    Raises:
        - ValueError: key is neither old_root nor below it.
    """
    if key == old_root:
        return new_root
    if not key.startswith(old_root + SEPARATOR):
        raise ValueError("the key is not below the moved root")
    return new_root + key[len(old_root) :]


def qualify(prefix: str, key: str) -> str:
    """
    Qualify a key with its project prefix.

    Args:
        - prefix (str): the project key prefix.
        - key (str): the unqualified key.

    Returns:
        - key (str): "<prefix>:<key>".
    """
    return f"{prefix}{QUALIFIER}{key}"
