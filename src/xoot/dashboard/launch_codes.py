"""
One-time launch codes for `xoot dashboard --open`.

The browser opener runs as a separate process whose argv any local user can
read, so it never receives the session token. It gets a launch code
instead: random, valid for LAUNCH_TTL_S seconds, redeemable once, and worth
nothing but one exchange for the session cookie.
"""

import hmac
import secrets
import time
from collections.abc import Callable

LAUNCH_TTL_S = 30.0
CODE_BYTES = 32


class LaunchCodes:
    """Issues codes and redeems each at most once, within its lifetime."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        """
        Start with no codes.

        Args:
            - clock (Callable[[], float]): a monotonic clock in seconds;
              tests pass their own.
        """
        self._clock = clock
        self._codes: dict[str, float] = {}

    def issue(self) -> str:
        """
        Create a new code.

        Returns:
            - code (str): the code, URL-safe.
        """
        code = secrets.token_urlsafe(CODE_BYTES)
        self._codes[code] = self._clock() + LAUNCH_TTL_S
        return code

    def redeem(self, offered: str) -> bool:
        """
        Spend a code: it is removed whether or not it was still valid.

        Args:
            - offered (str): the code from the query string.

        Returns:
            - valid (bool): True only for an unspent code within its TTL.
        """
        now = self._clock()
        match = None
        for code in list(self._codes):
            if _same(code, offered):
                match = code
        if match is None:
            return False
        expires = self._codes.pop(match)
        return now < expires


def _same(expected: str, offered: str) -> bool:
    """Compare in constant time; non-ASCII input never matches."""
    try:
        return hmac.compare_digest(expected.encode("ascii"), offered.encode("ascii"))
    except UnicodeEncodeError:
        return False
