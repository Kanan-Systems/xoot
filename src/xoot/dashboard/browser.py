"""
Opening the dashboard URL in a browser, best effort.

Under WSL the Linux openers rarely reach the Windows browser, so wslview is
used there; elsewhere Python's webbrowser picks the platform opener.
"""

import os
import subprocess
import webbrowser

OPEN_TIMEOUT_S = 15


def open_url(url: str) -> bool:
    """
    Ask the desktop to open a URL.

    Args:
        - url (str): the URL, token included.

    Returns:
        - opened (bool): False when no opener ran successfully.
    """
    if os.environ.get("WSL_DISTRO_NAME"):
        try:
            subprocess.run(
                ["wslview", url],
                check=True,
                timeout=OPEN_TIMEOUT_S,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return True
    try:
        return webbrowser.open(url)
    except webbrowser.Error:
        return False
