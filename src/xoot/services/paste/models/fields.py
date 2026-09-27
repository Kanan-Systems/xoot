"""
Field types shared by the paste ops.

A ref names a record created earlier in the same block; it is written
"$<name>" wherever a key is accepted. Keys and refs are the only input a
paste error may echo, so both are kept short and shape-checked.
"""

import re
from typing import Annotated

from pydantic import StringConstraints

REF_PREFIX = "$"
REF_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
KEY_MAX = 64

RefName = Annotated[str, StringConstraints(pattern=REF_NAME.pattern)]
"""The name an op gives its new record, without the leading "$"."""

KeyOrRef = Annotated[str, StringConstraints(min_length=1, max_length=KEY_MAX)]
"""A public key, or "$<ref>" for a record created earlier in the block."""


def is_ref(value: str) -> bool:
    """
    Tell whether a key field holds a ref rather than a key.

    Args:
        - value (str): the field value.

    Returns:
        - is_ref (bool): True when it starts with "$".
    """
    return value.startswith(REF_PREFIX)


def ref_name(value: str) -> str | None:
    """
    Return the name of a well-formed ref.

    Args:
        - value (str): a value that starts with "$".

    Returns:
        - name (str | None): the name after "$", or None when malformed.
    """
    name = value[len(REF_PREFIX) :]
    return name if REF_NAME.fullmatch(name) else None
