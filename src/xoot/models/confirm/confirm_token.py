"""A stored confirm-token row."""

from xoot.models.confirm.new_confirm_token import NewConfirmToken
from xoot.models.fields import Id, Timestamp


class ConfirmToken(NewConfirmToken):
    """
    An issued token: the inserted columns plus its id and used_at, which is
    set once, in the transaction of the write the token authorized.
    """

    id: Id
    used_at: Timestamp | None
