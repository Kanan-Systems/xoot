"""
The project a call's keys belong to, from their "<prefix>:" qualifiers.

Keys are unique only within a project, so every call that names keys works
in one project. It is found, in order, from the explicit project argument,
the keys' qualifier, the client's roots, then the working directory; the
resolvers take the qualifier from here and the keys go on unqualified.
"""

from collections.abc import Iterable

from xoot.exceptions.qualifier_error import QualifierError
from xoot.utils.keys import QUALIFIER, split_qualified

MIXED = "the keys name more than one project"
MALFORMED = "a key qualifier is not a project prefix"
CONFLICT = "a key is qualified with another project than the one named"


def key_qualifier(keys: Iterable[str | None]) -> str | None:
    """
    Return the one project prefix a call's qualified keys name.

    Args:
        - keys (Iterable[str | None]): every key argument of the call; None
          and unqualified keys are skipped.

    Returns:
        - prefix (str | None): the shared prefix, or None when no key is
          qualified.

    Raises:
        - QualifierError: a qualifier is malformed, or two differ.
    """
    found: str | None = None
    for key in keys:
        if key is None or QUALIFIER not in key:
            continue
        parts = split_qualified(key)
        if parts is None:
            raise QualifierError(MALFORMED)
        prefix = parts[0]
        if found is not None and prefix != found:
            raise QualifierError(MIXED)
        found = prefix
    return found


def unqualified(key: str) -> str:
    """
    Drop a key's "<prefix>:" qualifier, once the project is settled.

    A malformed qualifier is left in place, so the key fails the grammar
    and resolves to nothing.

    Args:
        - key (str): a key, qualified or not.

    Returns:
        - key (str): the key without its qualifier.
    """
    parts = split_qualified(key)
    return key if parts is None else parts[1]
