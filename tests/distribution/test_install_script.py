"""
install.sh, run against stub uv, claude and xoot executables.

PATH holds only the stubs (the script uses bash builtins otherwise), so no
test can reach the real uv or claude, install anything or change a client's
configuration. Each stub appends its arguments to one log file.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
TIMEOUT_S = 30.0

UV_STUB = """#!{bash}
printf '%s\\n' "uv $*" >> {log}
if [[ "$*" == "tool dir --bin" ]]; then printf '%s\\n' {bin_dir}; fi
"""
CLAUDE_STUB = """#!{bash}
printf '%s\\n' "claude $*" >> {log}
if [[ "$1 $2" == "mcp get" ]]; then [[ ${{STUB_REGISTERED:-0}} == 1 ]]; fi
"""
XOOT_STUB = """#!{bash}
printf '%s\\n' "xoot $*" >> {log}
printf 'xoot 0.1.0\\n'
"""


@dataclass(frozen=True)
class Result:
    """One install.sh run: its exit code, output and the stubs' log."""

    code: int
    out: str
    err: str
    calls: list[str]


@dataclass(frozen=True)
class Sandbox:
    """A fake checkout, the stubs' PATH directory and the tool bin directory."""

    checkout: Path
    stubs: Path
    bin_dir: Path
    log: Path

    def run(self, *args: str, cwd: Path | None = None, **env: str) -> Result:
        """
        Run install.sh with only the stubs on PATH.

        Args:
            - args (str): install.sh options.
            - cwd (Path | None): working directory; the checkout when None.
            - env (str): extra environment variables.

        Returns:
            - result (Result): the exit code, output and logged calls.
        """
        assert BASH is not None
        environment = {"PATH": str(self.stubs), "HOME": str(self.checkout.parent)}
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
        calls = (
            self.log.read_text(encoding="utf-8").splitlines()
            if self.log.exists()
            else []
        )
        return Result(done.returncode, done.stdout, done.stderr, calls)


def _stub(path: Path, template: str, **values: str) -> None:
    path.write_text(template.format(bash=BASH, **values), encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture(name="sandbox")
def fixture_sandbox(tmp_path: Path) -> Sandbox:
    """A checkout holding the real install.sh and pyproject.toml, plus stubs."""
    checkout, stubs, bin_dir = (tmp_path / d for d in ("xoot", "stubs", "tool-bin"))
    for directory in (checkout, stubs, bin_dir):
        directory.mkdir()
    for name in ("install.sh", "pyproject.toml"):
        shutil.copy2(REPO / name, checkout / name)
    log = tmp_path / "calls.log"
    _stub(stubs / "uv", UV_STUB, log=str(log), bin_dir=str(bin_dir))
    _stub(stubs / "claude", CLAUDE_STUB, log=str(log))
    _stub(bin_dir / "xoot", XOOT_STUB, log=str(log))
    return Sandbox(checkout, stubs, bin_dir, log)


def _actions(out: str) -> list[str]:
    return [line[2:] for line in out.splitlines() if line.startswith("+ ")]


def _snippet(out: str) -> dict[str, dict[str, object]]:
    """The printed "mcpServers" fragment, wrapped into a JSON object."""
    lines = out.splitlines()
    start = lines.index('  "mcpServers": {')
    end = lines.index("  }", start)
    return json.loads("{" + "\n".join(lines[start : end + 1]) + "}")


def test_dry_run_prints_every_action_and_runs_nothing(sandbox: Sandbox) -> None:
    """--dry-run calls no stub and prints each command it would run."""
    result = sandbox.run("--dry-run")
    assert result.code == 0, result.err
    assert not result.calls
    assert _actions(result.out) == [
        "uv tool install --reinstall .",
        "uv tool dir --bin",
        "<uv tool dir --bin>/xoot --version",
        "claude mcp get xoot",
        "claude mcp add xoot --scope user -- <uv tool dir --bin>/xoot-mcp",
    ]


def test_yes_installs_and_registers(sandbox: Sandbox) -> None:
    """--yes installs the checkout and registers xoot-mcp at user scope."""
    result = sandbox.run("--yes")
    assert result.code == 0, result.err
    expected = [
        "uv tool install --reinstall .",
        "uv tool dir --bin",
        f"{sandbox.bin_dir}/xoot --version",
        "claude mcp get xoot",
        f"claude mcp add xoot --scope user -- {sandbox.bin_dir}/xoot-mcp",
    ]
    assert result.calls == [
        "uv tool install --reinstall .",
        "uv tool dir --bin",
        "xoot --version",
        "claude mcp get xoot",
        f"claude mcp add xoot --scope user -- {sandbox.bin_dir}/xoot-mcp",
    ]
    assert _actions(result.out) == expected
    assert "xoot init" in result.out and "docs/clients.md" in result.out


def test_already_registered_is_skipped(sandbox: Sandbox) -> None:
    """When claude mcp get finds xoot, nothing is added."""
    result = sandbox.run("--yes", STUB_REGISTERED="1")
    assert result.code == 0, result.err
    assert result.calls[-1] == "claude mcp get xoot"
    assert not any(call.startswith("claude mcp add") for call in result.calls)
    assert "already registered" in result.out


def test_no_terminal_without_yes_does_not_register(sandbox: Sandbox) -> None:
    """Without --yes and a terminal the answer is no; the command is shown."""
    result = sandbox.run()
    assert result.code == 0, result.err
    assert not any(call.startswith("claude mcp add") for call in result.calls)
    assert f"claude mcp add xoot --scope user -- {sandbox.bin_dir}/xoot-mcp" in (
        result.out
    )


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
    result = sandbox.run("--yes", PATH=f"{sandbox.stubs}:{sandbox.bin_dir}")
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
