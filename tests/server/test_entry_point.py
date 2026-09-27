"""The xoot-mcp console script and python -m xoot.server share one main."""

from importlib.metadata import entry_points

from xoot.server import __main__ as server_main


def test_console_script_runs_main() -> None:
    """xoot-mcp is installed and points at xoot.server.__main__:main."""
    (script,) = entry_points(group="console_scripts", name="xoot-mcp")
    assert script.value == "xoot.server.__main__:main"
    assert script.load() is server_main.main
