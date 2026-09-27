"""
Services sit below the MCP server: no module under xoot/services imports
xoot.server, so services (paste mode included) never depend on tool code.
"""

import ast
from pathlib import Path

import xoot.services

SERVICES = Path(xoot.services.__file__).parent


def _server_imports(path: Path) -> list[str]:
    """Every import in a module that names xoot.server or a module under it."""
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            names = [module, *(f"{module}.{alias.name}" for alias in node.names)]
        else:
            continue
        found.extend(
            name
            for name in names
            if name == "xoot.server" or name.startswith("xoot.server.")
        )
    return found


def test_no_service_imports_the_server() -> None:
    """Walk every module under services/ and find no xoot.server import."""
    modules = sorted(SERVICES.rglob("*.py"))
    assert len(modules) > 30
    offenders = {
        str(path.relative_to(SERVICES)): imports
        for path in modules
        if (imports := _server_imports(path))
    }
    assert not offenders


def test_the_walk_detects_a_server_import(tmp_path: Path) -> None:
    """The check itself catches each import form."""
    for source in (
        "import xoot.server.errors\n",
        "from xoot.server.schemas import item_summary\n",
        "from xoot import server\n",
    ):
        module = tmp_path / "m.py"
        module.write_text(source, encoding="utf-8")
        assert _server_imports(module), source
