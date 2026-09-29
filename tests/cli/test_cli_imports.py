"""The CLI loads the web stack only inside `xoot dashboard`."""

import subprocess
import sys

PROBE = """
import sys
from xoot.cli.__main__ import main
from xoot.cli import parser
parser.build_parser().parse_args(["brief"])
loaded = sorted(m for m in sys.modules if m.split(".")[0] in ("starlette", "uvicorn"))
print(",".join(loaded))
"""


def test_cli_never_imports_starlette_or_uvicorn() -> None:
    """Importing the CLI and building its parser leaves the web stack unloaded."""
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert result.stdout.strip() == ""
