"""
Annotated argument types shared by the tool signatures.

The SDK derives each tool's input schema from its signature, so the
descriptions here are what the model reads for every argument.
"""

from typing import Annotated

from pydantic import Field

from xoot.models.confirm.confirmation import TOKEN_MAX
from xoot.models.fields import Id
from xoot.utils.keys import KEY_MAX

ItemKey = Annotated[
    str,
    Field(
        max_length=KEY_MAX,
        description=(
            "Item key: goal-<n>, goal-<n>/batch-<m>, goal-<n>/batch-<m>/subtask-<k>, "
            "or a backlog key (backlog-<k>, goal-<n>/backlog-<k>, "
            "goal-<n>/batch-<m>/backlog-<k>). May be qualified as <prefix>:<key>."
        ),
    ),
]
OptionalItemKey = Annotated[
    str | None,
    Field(max_length=KEY_MAX, description="Item key, optionally <prefix>:<key>."),
]
DecisionKey = Annotated[
    str,
    Field(
        max_length=KEY_MAX,
        description=(
            "Decision key: <goal, batch or subtask key>/decision-<n>. May be "
            "qualified as <prefix>:<key>."
        ),
    ),
]
ProjectAlias = Annotated[
    str | None,
    Field(
        description=(
            "Project alias or key prefix. Leave it out to take the project from "
            "a <prefix>:<key> key, then the client's roots, then the server's "
            "working directory. Chat clients pass it."
        )
    ),
]
ExpectedVersion = Annotated[
    Id, Field(description="The version from your last read of this record.")
]
ConfirmToken = Annotated[
    str | None,
    Field(
        max_length=TOKEN_MAX,
        description=(
            "Leave out to get a preview and a confirm_token. To apply, call "
            "again with the same arguments plus that token (single use, 5 minutes)."
        ),
    ),
]
