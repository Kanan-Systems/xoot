"""
Field types shared by the paste ops.

A ref names a record created earlier in the same block; it is written
"$<name>" wherever a key is accepted. Every key field is checked against the
key grammar at parse time, item keys and decision keys apart, and a refused
value is never echoed: the error names the field and a fixed error type.
"""

import re
from typing import Annotated

from pydantic import AfterValidator, StringConstraints
from pydantic_core import PydanticCustomError

from xoot.utils.keys import KEY_MAX, is_decision_key, is_item_key

REF_PREFIX = "$"
REF_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

RefName = Annotated[str, StringConstraints(pattern=REF_NAME.pattern)]
"""The name an op gives its new record, without the leading "$"."""


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


def check_item_key_or_ref(value: str) -> str:
    """
    Accept an item key (qualified or not) or a well-formed ref.

    Args:
        - value (str): the field value.

    Returns:
        - value (str): the same value.

    Raises:
        - PydanticCustomError: neither; the message never quotes the value.
    """
    if (is_ref(value) and ref_name(value) is not None) or is_item_key(value):
        return value
    raise PydanticCustomError("item_key", "not an item key or $ref")


def check_decision_key_or_ref(value: str) -> str:
    """
    Accept a decision key (qualified or not) or a well-formed ref.

    Args:
        - value (str): the field value.

    Returns:
        - value (str): the same value.

    Raises:
        - PydanticCustomError: neither; the message never quotes the value.
    """
    if (is_ref(value) and ref_name(value) is not None) or is_decision_key(value):
        return value
    raise PydanticCustomError("decision_key", "not a decision key or $ref")


ItemKeyOrRef = Annotated[
    str,
    StringConstraints(min_length=1, max_length=KEY_MAX),
    AfterValidator(check_item_key_or_ref),
]
"""An item key, or "$<ref>" for an item created earlier in the block."""

DecisionKeyOrRef = Annotated[
    str,
    StringConstraints(min_length=1, max_length=KEY_MAX),
    AfterValidator(check_decision_key_or_ref),
]
"""A decision key, or "$<ref>" for a decision recorded earlier in the block."""
