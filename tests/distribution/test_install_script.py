"""
install.sh, run against stub uv, claude and xoot executables.

PATH holds only the stubs plus the real mktemp and rm (the script uses bash
builtins otherwise), so no test can reach the real uv or claude, install
anything or change a client's configuration. Each stub appends its
arguments to one log file; TMPDIR is private, so leftover temp files show.
"""

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
SYSTEM_TOOLS = ("mktemp", "rm")
TIMEOUT_S = 30.0
PIN = "anyio==4.15.1"

# export writes a pin to its -o file; tool install logs the constraints it
# was given, while the file still exists, and fails on request; tool dir
# --bin prints STUB_BIN_DIR when set, as uv does for a custom XDG_DATA_HOME.
UV_STUB = """#!{bash}
printf '%s\\n' "uv $*" >> {log}
if [[ $1 == export ]]; then
    while (($#)); do [[ $1 == -o ]] && printf '{pin}\\n' > "$2"; shift; done
elif [[ "$1 $2" == "tool install" ]]; then
    while (($#)); do
        [[ $1 == --constraints ]] && printf 'constraints: %s\\n' "$(<"$2")" >> {log}
        shift
    done
    [[ ${{STUB_INSTALL_FAIL:-0}} != 1 ]]
elif [[ "$*" == "tool dir --bin" ]]; then
    printf '%s\\n' "${{STUB_BIN_DIR:-{bin_dir}}}"
fi
"""
CLAUDE_STUB = """#!{bash}
printf '%s\\n' "claude $*" >> {log}
if [[ "$1 $2" == "plugin list" ]]; then printf '%s\\n' "${{STUB_PLUGINS:-}}"; fi
if [[ "$1 $2" == "mcp get" ]]; then [[ ${{STUB_MCP:-0}} == 1 ]]; fi
"""
XOOT_STUB = """#!{bash}
printf '%s\\n' "xoot $*" >> {log}
printf 'xoot 0.1.0\\n'
"""
OTHER_PLUGINS = "Installed plugins:\n  code-review@claude-plugins-official"
EXPORT = (
    "uv export --quiet --frozen --no-dev --no-emit-project "
    "--format requirements-txt -o {file}"
)
INSTALL = "uv tool install --reinstall --constraints {file} ."


@dataclass(frozen=True)
class Result:
    """One install.sh run: its exit code, output and the stubs' log."""

    code: int
    out: str
    err: str
    calls: list[str]


@dataclass(frozen=True)
class Sandbox:
    """A fake checkout, stub and tool directories, the log and a private TMPDIR."""

    checkout: Path
    stubs: Path
    system: Path
    bin_dir: Path
    log: Path
    tmp: Path

    @property
    def path(self) -> str:
        """The PATH install.sh runs with: stubs, then mktemp and rm."""
        return f"{self.stubs}:{self.system}"

    def run(self, *args: str, cwd: Path | None = None, **env: str) -> Result:
        """
        Run install.sh with only the stubs, mktemp and rm on PATH.

        Temp-file paths in the output and the log read as <tmp>.

        Args:
            - args (str): install.sh options.
            - cwd (Path | None): working directory; the checkout when None.
            - env (str): extra environment variables.

        Returns:
            - result (Result): the exit code, output and logged calls.
        """
        assert BASH is not None
        environment = {
            "PATH": self.path,
            "HOME": str(self.checkout.parent),
            "TMPDIR": str(self.tmp),
            "STUB_PLUGINS": OTHER_PLUGINS,
        }
        environment.update(env)
        done = subprocess.run(
            [BASH, str(self.checkout / "install.sh"), *args],
            cwd=cwd or self.checkout,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            check=False,
        )
        log = self.log.read_text(encoding="utf-8") if self.log.exists() else ""
        return Result(
            done.returncode,
            self._mask(done.stdout),
            done.stderr,
            self._mask(log).splitlines(),
        )

    def _mask(self, text: str) -> str:
        return re.sub(re.escape(str(self.tmp)) + r"/\S+", "<tmp>", text)


def _stub(path: Path, template: str, **values: str) -> None:
    path.write_text(template.format(bash=BASH, **values), encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture(name="sandbox")
def fixture_sandbox(tmp_path: Path) -> Sandbox:
    """A checkout holding the real install.sh and pyproject.toml, plus stubs."""
    names = ("xoot", "stubs", "system", "tool-bin", "tmp")
    checkout, stubs, system, bin_dir, tmp = (tmp_path / name for name in names)
    for directory in (checkout, stubs, system, bin_dir, tmp):
        directory.mkdir()
    for name in ("install.sh", "pyproject.toml"):
        shutil.copy2(REPO / name, checkout / name)
    for tool in SYSTEM_TOOLS:
        real = shutil.which(tool)
        assert real is not None, f"{tool} is not installed"
        (system / tool).symlink_to(real)
    log = tmp_path / "calls.log"
    _stub(stubs / "uv", UV_STUB, log=str(log), bin_dir=str(bin_dir), pin=PIN)
    _stub(stubs / "claude", CLAUDE_STUB, log=str(log))
    _stub(bin_dir / "xoot", XOOT_STUB, log=str(log))
    return Sandbox(checkout, stubs, system, bin_dir, log, tmp)


def _actions(out: str) -> list[str]:
    return [line[2:] for line in out.splitlines() if line.startswith("+ ")]


def _snippet(out: str) -> dict[str, dict[str, object]]:
    """The printed "mcpServers" fragment, wrapped into a JSON object."""
    lines = out.splitlines()
    start = lines.index('  "mcpServers": {')
    end = lines.index("  }", start)
    return json.loads("{" + "\n".join(lines[start : end + 1]) + "}")


def _plugin_install(checkout: Path) -> list[str]:
    return [
        f"claude plugin marketplace add --scope user {checkout}",
        "claude plugin install --scope user xoot@xoot",
    ]


def _no_mcp_add(result: Result) -> bool:
    return not any(call.startswith("claude mcp add") for call in result.calls)


def test_dry_run_prints_every_action_and_runs_nothing(sandbox: Sandbox) -> None:
    """--dry-run calls no stub, creates no temp file and prints each command."""
    result = sandbox.run("--dry-run")
    assert result.code == 0, result.err
    assert not result.calls
    assert not list(sandbox.tmp.iterdir())
    assert _actions(result.out) == [
        "mktemp",
        EXPORT.format(file="<temp file>"),
        INSTALL.format(file="<temp file>"),
        "uv tool dir --bin",
        "<uv tool dir --bin>/xoot --version",
        "claude plugin list",
        "claude mcp get xoot",
        *_plugin_install(sandbox.checkout),
    ]


def test_yes_installs_locked_and_adds_plugin(sandbox: Sandbox) -> None:
    """--yes exports the lock, installs with it, then installs the plugin."""
    result = sandbox.run("--yes")
    assert result.code == 0, result.err
    assert result.calls == [
        EXPORT.format(file="<tmp>"),
        INSTALL.format(file="<tmp>"),
        f"constraints: {PIN}",
        "uv tool dir --bin",
        "xoot --version",
        "claude plugin list",
        "claude mcp get xoot",
        *_plugin_install(sandbox.checkout),
    ]
    assert _actions(result.out) == [
        "mktemp",
        EXPORT.format(file="<tmp>"),
        INSTALL.format(file="<tmp>"),
        "uv tool dir --bin",
        f"{sandbox.bin_dir}/xoot --version",
        "claude plugin list",
        "claude mcp get xoot",
        *_plugin_install(sandbox.checkout),
        "rm -f <tmp>",
    ]
    assert "xoot init" in result.out and "docs/clients.md" in result.out


def test_constraints_file_is_removed(sandbox: Sandbox) -> None:
    """The exported constraints file is gone once the script ends."""
    result = sandbox.run("--yes")
    assert result.code == 0, result.err
    assert not list(sandbox.tmp.iterdir())


def test_constraints_file_is_removed_on_failure(sandbox: Sandbox) -> None:
    """A failed install stops the script and still removes the temp file."""
    result = sandbox.run("--yes", STUB_INSTALL_FAIL="1")
    assert result.code == 1
    assert result.calls[-1] == f"constraints: {PIN}"
    assert _actions(result.out)[-1] == "rm -f <tmp>"
    assert not list(sandbox.tmp.iterdir())


def test_existing_plugin_is_skipped(sandbox: Sandbox) -> None:
    """A xoot plugin in claude plugin list means nothing else is registered."""
    plugins = f"{OTHER_PLUGINS}\n  xoot@xoot"
    result = sandbox.run("--yes", STUB_PLUGINS=plugins)
    assert result.code == 0, result.err
    assert result.calls[-1] == "claude plugin list"
    assert "already installed as a Claude Code plugin" in result.out


def test_similar_plugin_name_is_not_xoot(sandbox: Sandbox) -> None:
    """A plugin whose name merely ends in xoot does not count."""
    result = sandbox.run("--yes", STUB_PLUGINS="  myxoot@elsewhere")
    assert result.code == 0, result.err
    assert result.calls[-2:] == _plugin_install(sandbox.checkout)


def test_existing_mcp_server_is_skipped(sandbox: Sandbox) -> None:
    """A server registered with claude mcp add means no plugin is installed."""
    result = sandbox.run("--yes", STUB_MCP="1")
    assert result.code == 0, result.err
    assert result.calls[-1] == "claude mcp get xoot"
    assert "already registered as a Claude Code MCP server" in result.out
    assert _no_mcp_add(result)


def test_claude_mcp_add_is_never_called(sandbox: Sandbox) -> None:
    """Neither a fresh install nor a dry run registers with claude mcp add."""
    for args in (("--yes",), ("--dry-run",), ()):
        result = sandbox.run(*args)
        assert _no_mcp_add(result)
        assert "claude mcp add" not in result.out


def test_no_terminal_without_yes_does_not_install(sandbox: Sandbox) -> None:
    """Without --yes and a terminal the answer is no; the commands are shown."""
    result = sandbox.run()
    assert result.code == 0, result.err
    assert not any(
        call.startswith("claude plugin marketplace") for call in result.calls
    )
    for command in _plugin_install(sandbox.checkout):
        assert f"  {command}" in result.out


def test_missing_uv_exits_with_instructions(sandbox: Sandbox) -> None:
    """Without uv on PATH the script stops before any action."""
    (sandbox.stubs / "uv").unlink()
    result = sandbox.run("--yes")
    assert result.code == 1
    assert not result.calls
    assert "uv is not on PATH" in result.err
    assert "https://docs.astral.sh/uv/" in result.err


def test_missing_claude_skips_registration(sandbox: Sandbox) -> None:
    """Without claude on PATH the install still completes."""
    (sandbox.stubs / "claude").unlink()
    result = sandbox.run("--yes")
    assert result.code == 0, result.err
    assert not any(call.startswith("claude") for call in result.calls)
    assert "claude is not on PATH" in result.out


def test_wsl_prints_desktop_snippet(sandbox: Sandbox) -> None:
    """With WSL_DISTRO_NAME set, the snippet names the distro and full path."""
    result = sandbox.run("--yes", WSL_DISTRO_NAME="Ubuntu-24.04")
    assert result.code == 0, result.err
    assert _snippet(result.out) == {
        "mcpServers": {
            "xoot": {
                "command": "wsl.exe",
                "args": ["-d", "Ubuntu-24.04", f"{sandbox.bin_dir}/xoot-mcp"],
            }
        }
    }
    assert "Task Manager" in result.out
    assert "--db" not in result.out


def test_wsl_snippet_names_db_when_xdg_is_custom(sandbox: Sandbox) -> None:
    """A custom XDG_DATA_HOME, which Desktop does not pass, is spelled out."""
    result = sandbox.run("--yes", WSL_DISTRO_NAME="Debian", XDG_DATA_HOME="/data")
    assert result.code == 0, result.err
    assert '"--db", "/data/xoot/xoot.db"' in result.out


def test_wsl_snippet_escapes_json(sandbox: Sandbox) -> None:
    """A quote or backslash in the distro name still yields valid JSON."""
    result = sandbox.run("--yes", WSL_DISTRO_NAME='odd"name\\x')
    assert result.code == 0, result.err
    entry = _snippet(result.out)["mcpServers"]["xoot"]
    assert isinstance(entry, dict) and entry["args"][1] == 'odd"name\\x'


def test_no_snippet_outside_wsl(sandbox: Sandbox) -> None:
    """Without WSL_DISTRO_NAME no Desktop snippet is printed."""
    result = sandbox.run("--yes")
    assert "mcpServers" not in result.out


def test_not_repo_root_exits(sandbox: Sandbox, tmp_path: Path) -> None:
    """Run from elsewhere, the script refuses before any action."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = sandbox.run("--yes", cwd=elsewhere)
    assert result.code == 1
    assert not result.calls
    assert "root of the xoot checkout" in result.err


def test_other_project_is_not_repo_root(sandbox: Sandbox) -> None:
    """A pyproject.toml naming another project is refused too."""
    pyproject = sandbox.checkout / "pyproject.toml"
    pyproject.write_text('[project]\nname = "other"\n', encoding="utf-8")
    result = sandbox.run("--yes")
    assert result.code == 1
    assert not result.calls


def test_bin_dir_off_path_warns(sandbox: Sandbox) -> None:
    """The tool bin directory missing from PATH is a warning, not an error."""
    result = sandbox.run("--yes")
    assert result.code == 0
    assert f"{sandbox.bin_dir} is not on PATH" in result.err


def test_bin_dir_on_path_does_not_warn(sandbox: Sandbox) -> None:
    """With the tool bin directory on PATH there is no warning."""
    result = sandbox.run("--yes", PATH=f"{sandbox.path}:{sandbox.bin_dir}")
    assert result.code == 0
    assert "not on PATH" not in result.err


def test_help_runs_nothing(sandbox: Sandbox) -> None:
    """--help prints usage and exits 0 without any action."""
    result = sandbox.run("--help")
    assert result.code == 0
    assert result.out.startswith("Usage: ./install.sh")
    assert not result.calls


def test_unknown_option_is_usage_error(sandbox: Sandbox) -> None:
    """An unknown option exits 2 before any action."""
    result = sandbox.run("--force")
    assert result.code == 2
    assert "unknown option: --force" in result.err
    assert not result.calls


def test_dotted_bin_dir_on_path_is_normalized(sandbox: Sandbox, tmp_path: Path) -> None:
    """uv's <data>/../bin matches its plain spelling on PATH and in the snippet."""
    (tmp_path / "data").mkdir()
    real = (tmp_path / "tool-bin").resolve()
    result = sandbox.run(
        "--yes",
        STUB_BIN_DIR=f"{tmp_path}/data/../tool-bin",
        PATH=f"{sandbox.path}:{sandbox.bin_dir}",
        WSL_DISTRO_NAME="Ubuntu",
    )
    assert result.code == 0, result.err
    assert "not on PATH" not in result.err
    assert f"{real}/xoot --version" in _actions(result.out)
    entry = _snippet(result.out)["mcpServers"]["xoot"]
    assert isinstance(entry, dict) and entry["args"][2] == f"{real}/xoot-mcp"
    assert ".." not in result.out


def test_dotted_path_entry_matches_bin_dir(sandbox: Sandbox, tmp_path: Path) -> None:
    """A PATH entry spelled with .. is normalized before the comparison."""
    (tmp_path / "data").mkdir()
    dotted = f"{tmp_path}/data/../tool-bin/"
    result = sandbox.run("--yes", PATH=f"{sandbox.path}:{dotted}")
    assert result.code == 0, result.err
    assert "not on PATH" not in result.err


def test_dotted_bin_dir_off_path_warns(sandbox: Sandbox, tmp_path: Path) -> None:
    """Off PATH, the warning names the normalized directory."""
    (tmp_path / "data").mkdir()
    real = (tmp_path / "tool-bin").resolve()
    result = sandbox.run("--yes", STUB_BIN_DIR=f"{tmp_path}/data/../tool-bin")
    assert result.code == 0, result.err
    assert f"warning: {real} is not on PATH" in result.err
    assert ".." not in result.err


def test_failed_bin_dir_lookup_stops(sandbox: Sandbox) -> None:
    """If uv cannot name its bin directory, nothing is checked or registered."""
    (sandbox.stubs / "uv").write_text(
        f"#!{BASH}\n[[ $1 != tool || $2 != dir ]]\n", encoding="utf-8"
    )
    result = sandbox.run("--yes")
    assert result.code != 0
    assert not any(call.startswith("claude") for call in result.calls)
    assert "--version" not in result.out
