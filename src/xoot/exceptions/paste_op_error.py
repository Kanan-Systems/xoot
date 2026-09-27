"""Raised when one op of a paste block fails, refusing the whole block."""

from xoot.exceptions.paste_error import PasteError


class PasteOpError(PasteError):
    """
    Op <index> of the block failed, so nothing in the block was written.

    Either reason holds a safe message built here (keys, refs and fixed
    text), or cause holds the domain or validation error the op raised, for
    the caller to render with its own safe-message rules.
    """

    def __init__(
        self,
        index: int,
        op: str,
        *,
        reason: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        Record which op failed and why.

        Args:
            - index (int): the op's 1-based position in the block.
            - op (str): the op name, e.g. "item_update".
            - reason (str | None): a safe reason, when the failure was found
              here.
            - cause (Exception | None): the error the op raised, otherwise.
        """
        prefix = f"op {index} ({op})"
        super().__init__(prefix if reason is None else f"{prefix}: {reason}")
        self.index = index
        self.op = op
        self.prefix = prefix
        self.reason = reason
        self.cause = cause
