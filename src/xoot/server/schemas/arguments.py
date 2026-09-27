"""
Annotated argument types shared by the tool signatures.

The SDK derives each tool's input schema from its signature, so the
descriptions here are what the model reads for every argument.
"""

from typing import Annotated

from pydantic import Field

from xoot.models.confirm.confirmation import TOKEN_MAX
from xoot.models.fields import Id

SessionKey = Annotated[
    str, Field(description="Key of an open session, <prefix>-S<n>, from session_start.")
]
ItemKey = Annotated[str, Field(description="Item key, <prefix>-<n>.")]
DecisionKey = Annotated[str, Field(description="Decision key, <prefix>-D<n>.")]
ProjectAlias = Annotated[
    str | None,
    Field(
        description=(
            "Project alias. Leave it out to resolve the project from the "
            "client's roots, then from the server's working directory."
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
