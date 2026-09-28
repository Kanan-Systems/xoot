#!/usr/bin/env bash
# Install xoot from this checkout as a uv tool and optionally register it
# with Claude Code.
#
# Every action is printed before it runs. The script never uses sudo, never
# downloads anything itself (uv resolves the dependencies), never edits shell
# rc files and never writes Windows files: the Claude Desktop snippet is only
# printed. It uses bash builtins only, besides uv, claude and xoot.

set -euo pipefail

readonly UV_INSTALL_URL="https://docs.astral.sh/uv/getting-started/installation/"

dry_run=0
assume_yes=0

usage() {
    printf '%s\n' \
        "Usage: ./install.sh [--dry-run] [--yes] [--help]" \
        "" \
        "Run from the root of a xoot checkout (ideally a release tag). Installs" \
        "the checkout with 'uv tool install', checks 'xoot --version', and, when" \
        "'claude' is on PATH, offers to register xoot-mcp with Claude Code at" \
        "user scope." \
        "" \
        "  --dry-run  print every action, execute none" \
        "  --yes      register with Claude Code without asking" \
        "  --help     show this help"
}

say() {
    printf '%s\n' "$*"
}

warn() {
    printf 'warning: %s\n' "$*" >&2
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

# Prints the command, then runs it unless this is a dry run.
run() {
    say "+ $*"
    if ((dry_run)); then
        return 0
    fi
    "$@"
}

confirm() {
    local answer=""
    if ((assume_yes)); then
        return 0
    fi
    if [[ ! -t 0 ]]; then
        say "No terminal to ask on; skipping. Pass --yes to register."
        return 1
    fi
    read -r -p "$1 [y/N] " answer
    [[ $answer == [yY] || $answer == [yY][eE][sS] ]]
}

json_string() {
    local value=$1
    value=${value//\\/\\\\}
    value=${value//\"/\\\"}
    printf '"%s"' "$value"
}

# The [project] table's name, read with builtins so no parser is needed.
project_name() {
    local line section=""
    local name_re='^name[[:space:]]*=[[:space:]]*"([^"]*)"'
    [[ -f pyproject.toml ]] || return 0
    while IFS= read -r line || [[ -n $line ]]; do
        if [[ $line =~ ^\[([^]]*)\] ]]; then
            section=${BASH_REMATCH[1]}
        elif [[ $section == project && $line =~ $name_re ]]; then
            printf '%s' "${BASH_REMATCH[1]}"
            return 0
        fi
    done <pyproject.toml
}

on_path() {
    [[ ":$PATH:" == *":$1:"* ]]
}

parse_args() {
    local arg
    for arg in "$@"; do
        case $arg in
        --dry-run) dry_run=1 ;;
        --yes) assume_yes=1 ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            usage >&2
            printf 'error: unknown option: %s\n' "$arg" >&2
            exit 2
            ;;
        esac
    done
}

check_repo_root() {
    if [[ $(project_name) != xoot ]]; then
        die "run this from the root of the xoot checkout (no pyproject.toml" \
            "naming xoot in $PWD)"
    fi
}

check_uv() {
    if ! command -v uv >/dev/null 2>&1; then
        printf 'error: uv is not on PATH.\n' >&2
        printf 'Install uv (see %s), then run ./install.sh again.\n' \
            "$UV_INSTALL_URL" >&2
        exit 1
    fi
}

# --reinstall rebuilds from the checkout even when a tool of the same name
# and version is installed, so rerunning after checking out a new tag
# always installs what is on disk.
install_tool() {
    say "Installing xoot from $PWD"
    run uv tool install --reinstall .
}

# main prints the action: whatever this writes to stdout is captured.
tool_bin_dir() {
    if ((dry_run)); then
        printf '%s' '<uv tool dir --bin>'
        return 0
    fi
    uv tool dir --bin
}

check_install() {
    local bin_dir=$1
    run "$bin_dir/xoot" --version
    if ((dry_run)); then
        say "(dry run) would check that $bin_dir is on PATH"
    elif ! on_path "$bin_dir"; then
        warn "$bin_dir is not on PATH; add it to use xoot and xoot-mcp by name." \
            "This script does not edit shell rc files."
    fi
}

register_claude_code() {
    local bin_dir=$1
    if ! command -v claude >/dev/null 2>&1; then
        say "claude is not on PATH; skipping Claude Code registration."
        return 0
    fi
    if ((dry_run)); then
        run claude mcp get xoot
        run claude mcp add xoot --scope user -- "$bin_dir/xoot-mcp"
        return 0
    fi
    say "+ claude mcp get xoot"
    if claude mcp get xoot >/dev/null 2>&1; then
        say "xoot is already registered with Claude Code; skipping."
        return 0
    fi
    if confirm "Register xoot-mcp with Claude Code at user scope?"; then
        run claude mcp add xoot --scope user -- "$bin_dir/xoot-mcp"
    else
        say "Not registered. To do it later:"
        say "  claude mcp add xoot --scope user -- $bin_dir/xoot-mcp"
    fi
}

print_desktop_snippet() {
    local bin_dir=$1
    local distro=${WSL_DISTRO_NAME:-}
    if [[ -z $distro ]]; then
        return 0
    fi
    say ""
    say "Claude Desktop on Windows: open Settings > Developer > Edit Config and"
    say "add this xoot entry inside the existing \"mcpServers\" object:"
    say ""
    say "  \"mcpServers\": {"
    say "    \"xoot\": {"
    say "      \"command\": \"wsl.exe\","
    say "      \"args\": [\"-d\", $(json_string "$distro"), $(json_string "$bin_dir/xoot-mcp")]"
    say "    }"
    say "  }"
    say ""
    if [[ -n ${XDG_DATA_HOME:-} ]]; then
        say "XDG_DATA_HOME is set here but Claude Desktop does not pass it: add"
        say "\"--db\", $(json_string "$XDG_DATA_HOME/xoot/xoot.db") to the args."
        say ""
    fi
    say "Then fully quit Claude Desktop (end it in Task Manager; closing the"
    say "window leaves it running) and start it again."
}

print_next_steps() {
    say ""
    say "Next steps:"
    say "  cd <your project> && xoot init --prefix <prefix>"
    say "  Client setup: $PWD/docs/clients.md"
}

main() {
    local bin_dir
    parse_args "$@"
    check_repo_root
    check_uv
    if ((dry_run)); then
        say "Dry run: printing every action, executing none."
    fi
    install_tool
    say "+ uv tool dir --bin"
    bin_dir=$(tool_bin_dir)
    check_install "$bin_dir"
    register_claude_code "$bin_dir"
    print_desktop_snippet "$bin_dir"
    print_next_steps
}

main "$@"
