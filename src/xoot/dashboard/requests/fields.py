"""Field types shared by the request bodies."""

from typing import Annotated

from pydantic import StringConstraints

from xoot.models.confirm.confirmation import TOKEN_MAX
from xoot.utils.keys import KEY_MAX

# An item or decision key; resolved in the path's project like the path keys.
RecordKey = Annotated[str, StringConstraints(min_length=1, max_length=KEY_MAX)]
# A confirm_token from a preview response.
Token = Annotated[str, StringConstraints(min_length=1, max_length=TOKEN_MAX)]
