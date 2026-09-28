#!/usr/bin/env bash
# Install xoot from this checkout as a uv tool, with the dependency versions
# pinned in uv.lock, and optionally install the Claude Code plugin.
#
# Every action is printed before it runs. The script never uses sudo, never
# downloads anything itself (uv resolves the dependencies), never edits shell
# rc files and never writes Windows files: the Claude Desktop snippet is only
# printed. Besides uv, claude and xoot it runs only mktemp and rm; everything
# else is a bash builtin.

set -euo pipefail

readonly UV_INSTALL_URL="https://docs.astral.sh/uv/getting-started/installation/"
# A xoot plugin from any marketplace, as `claude plugin list` names it.
readonly PLUGIN_RE='(^|[^[:alnum:]_.-])xoot@[[:alnum:]_.-]+'

dry_run=0
assume_yes=0
constraints=""

usage() {
    printf '%s\n' \
        "Usage: ./install.sh [--dry-run] [--yes] [--help]" \
        "" \
        "Run from the root of a xoot checkout (ideally a release tag). Installs" \
        "the checkout with 'uv tool install', pinned to uv.lock, checks" \
        "'xoot --version', and, when 'claude' is on PATH, offers to install the" \
        "xoot plugin for Claude Code at user scope." \
        "" \
        "  --dry-run  print every action, execute none" \
        "  --yes      install the Claude Code plugin without asking" \
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
        say "No terminal to ask on; skipping. Pass --yes to install it."
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

remove_constraints() {
    if [[ -n $constraints ]]; then
        say "+ rm -f $constraints"
        rm -f -- "$constraints"
    fi
}

# An absolute directory as its physical path, without "." or ".." parts,
# using only the cd and pwd builtins. uv prints $XDG_DATA_HOME/../bin as is,
# and PATH may spell the same directory another way. Anything that is not an
# existing absolute directory comes back unchanged.
normalize_dir() {
    local dir=""
    if [[ $1 == /* ]]; then
        dir=$(CDPATH='' cd -- "$1" 2>/dev/null && pwd -P) || dir=""
    fi
    printf '%s' "${dir:-$1}"
}

# $1 must already be normalized; each PATH entry is normalized to match.
on_path() {
    local entry
    local -a entries=()
    IFS=: read -r -a entries <<<"$PATH"
    for entry in "${entries[@]}"; do
        if [[ -n $entry && $(normalize_dir "$entry") == "$1" ]]; then
            return 0
        fi
    done
    return 1
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

# uv tool install has no --locked, so the runtime dependencies uv.lock pins
# (the versions CI tests) go in as constraints. --reinstall rebuilds from the
# checkout even when a tool of the same name and version is installed, so
# rerunning after checking out a new tag always installs what is on disk.
install_tool() {
    local file='<temp file>'
    say "Installing xoot from $PWD with the dependency versions in uv.lock"
    say "+ mktemp"
    if ! ((dry_run)); then
        constraints=$(mktemp)
        file=$constraints
    fi
    run uv export --quiet --frozen --no-dev --no-emit-project \
        --format requirements-txt -o "$file"
    run uv tool install --reinstall --constraints "$file" .
}

# main prints the action: whatever this writes to stdout is captured. The
# directory is normalized here, before the PATH check, the Claude Code
# registration and the Desktop snippet see it.
tool_bin_dir() {
    local dir
    if ((dry_run)); then
        printf '%s' '<uv tool dir --bin>'
        return 0
    fi
    dir=$(uv tool dir --bin) || return
    normalize_dir "$dir"
}

check_install() {
    local bin_dir=$1
    run "$bin_dir/xoot" --version
    if ((dry_run)); then
        say "(dry run) would check that $bin_dir is on PATH"
    elif ! on_path "$bin_dir"; then
        warn "$bin_dir is not on PATH; add it so xoot, and xoot-mcp for the" \
            "Claude Code plugin, are found by name. This script does not edit" \
            "shell rc files."
    fi
}

install_plugin() {
    run claude plugin marketplace add --scope user "$PWD"
    run claude plugin install --scope user xoot@xoot
}

# Either registration counts: two would serve the same tools twice.
register_claude_code() {
    local plugins=""
    if ! command -v claude >/dev/null 2>&1; then
        say "claude is not on PATH; skipping Claude Code registration."
        return 0
    fi
    if ((dry_run)); then
        run claude plugin list
        run claude mcp get xoot
        install_plugin
        return 0
    fi
    say "+ claude plugin list"
    plugins=$(claude plugin list 2>/dev/null) || plugins=""
    if [[ $plugins =~ $PLUGIN_RE ]]; then
        say "xoot is already installed as a Claude Code plugin; skipping."
        return 0
    fi
    say "+ claude mcp get xoot"
    if claude mcp get xoot >/dev/null 2>&1; then
        say "xoot is already registered as a Claude Code MCP server" \
            "(claude mcp); skipping."
        return 0
    fi
    if confirm "Install the xoot plugin (MCP server and skill) for Claude Code?"; then
        install_plugin
    else
        say "Not installed. To do it later:"
        say "  claude plugin marketplace add --scope user $PWD"
        say "  claude plugin install --scope user xoot@xoot"
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
    trap remove_constraints EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    check_repo_root
    check_uv
    if ((dry_run)); then
        say "Dry run: printing every action, executing none."
    fi
    install_tool
    say "+ uv tool dir --bin"
    bin_dir=$(tool_bin_dir)
    check_install "$bin_dir"
    register_claude_code
    print_desktop_snippet "$bin_dir"
    print_next_steps
}

main "$@"
