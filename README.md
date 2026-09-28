# xoot

Keep goals, batches and subtasks straight across Claude sessions.

[![Stars](https://img.shields.io/github/stars/Kanan-Systems/xoot?style=flat)](https://github.com/Kanan-Systems/xoot/stargazers)
[![License](https://img.shields.io/github/license/Kanan-Systems/xoot)](LICENSE)
[![backend-gates](https://github.com/Kanan-Systems/xoot/actions/workflows/backend-gates.yml/badge.svg)](https://github.com/Kanan-Systems/xoot/actions/workflows/backend-gates.yml)

xoot is a local-only tracker that Claude reads and writes through MCP. A
session starts with a brief and focus items, captures side work the moment it
appears, records decisions with their rationale, and closes by giving every
open item a disposition, so the next session picks up where this one stopped.
State lives in one SQLite file on your machine; nothing is sent anywhere.

## Status

0.1.0, alpha. The MCP server (stdio), the CLI and paste mode work; the
dashboard is not built yet.

## Install

Needs Linux (or WSL) and [uv](https://docs.astral.sh/uv/). From a clone,
check out a release tag and run the installer:

```sh
git clone https://github.com/Kanan-Systems/xoot.git
cd xoot
git checkout v0.1.0
./install.sh --dry-run     # prints every action, runs none
./install.sh               # --yes registers with Claude Code without asking
```

`install.sh` runs `uv tool install --reinstall .`, checks `xoot --version`,
offers to register `xoot-mcp` with Claude Code at user scope, and on WSL
prints the Claude Desktop config snippet. It never uses sudo, downloads
nothing itself and edits no shell rc or Windows files.

Manual alternative, from the same checkout:

```sh
uv tool install --reinstall .
claude mcp add xoot --scope user -- "$(uv tool dir --bin)/xoot-mcp"
```

## Quickstart

Register the project once, from its directory: `xoot init --prefix myapp`.

- **Claude Code**: registered by `install.sh`, `claude mcp add` or the
  [plugin](docs/clients.md#claude-code). Launch it inside the project
  directory; the project resolves from there.
- **Claude Desktop** (Windows with WSL): add the snippet `install.sh` prints
  to the config, then fully quit Desktop. Always pass the project. See
  [Claude Desktop on Windows](docs/clients.md#claude-desktop-on-windows-wsl).
- **Browser** (no MCP): `xoot paste brief`, paste it into the chat, then
  `xoot paste apply` the reply. See [Paste mode](#paste-mode).

## Docs

- [Concepts](docs/concepts.md): projects, items, sessions, backlogs,
  decisions, keys and history.
- [Clients](docs/clients.md): setup per client and the measured facts.
- [Workflow](docs/workflow.md): the session loop and working patterns.

## CLI

`xoot` (or `python -m xoot.cli`) is the user's own entry point. Every write
is recorded as the user, client `cli`, outside any session, except paste
mode's.

```sh
xoot init [PATH] --prefix xoot [--name N] [--alias A]...
xoot project list | show | add-alias A | remove-alias A | add-path P | remove-path P
xoot brief | tree [--root KEY] [--depth N] [--all]
xoot workflow export [-o FILE] | import FILE [--map kind:old=new]... [--yes]
xoot redact KEY FIELD [--yes]      # KEY: item, decision or session key, or a prefix
xoot paste brief | apply SOURCE [--yes]
xoot db stats | vacuum
xoot --version
```

`--project NAME` takes an alias or a key prefix; without it the project is
the one whose path contains the working directory. `--db PATH` and `--json`
work before or after the command. Results go to stdout; errors, warnings and
prompts to stderr. Commands that remove or rewrite data show the change and
ask y/N; without a terminal they need `--yes`. Exit codes: 0 ok, 1 refused,
2 usage, 3 database unavailable. `xoot-mcp --version` prints the version
without starting the server.

## Paste mode

For chats without MCP, `xoot paste` carries changes by copy and paste.
`xoot paste brief [--project NAME]` prints a markdown brief (at most 16 KiB):
the workflow, open sessions, items in flight with their versions, recent
decisions and the reply protocol. Paste it into the chat; Claude replies with
at most one fenced ```` ```xoot ```` JSON block of ops (session_start,
capture, item_create, item_update, decision_record, decision_update,
session_close). Copy the reply with the copy button under the whole message:
a code block's own copy button drops the fence lines. Then:

```sh
xoot paste apply reply.md        # or "-" to read stdin; at most 256 KiB
# WSL: define once, so no command is copied after copying the reply
alias xpaste='powershell.exe -NoProfile -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Clipboard -Raw" | xoot paste apply -'
xpaste                           # applies the reply on the Windows clipboard
```

Known limit: legacy code-page bytes are refused, but a code page can also
silently turn "—" into "-", or accents into "?". The plan warns about the
second (POSSIBLE ENCODING DAMAGE), so always read the titles in the plan.

`apply` dry-runs the whole block, prints the plan and a SIDE EFFECTS
section (auto-backlog moves) to stderr, and asks y/N on the terminal
(`/dev/tty`, since stdin may hold the paste); without a terminal it needs
`--yes`. The block applies in one transaction or not at all, and only if it
still does what the plan showed. Writes are recorded as `claude`, client
`paste`. stdout gets a ```` ```xoot-receipt ```` block (keys and versions,
never titles) to paste back so the next block uses current versions.

## Data

State lives in a local SQLite database at `$XDG_DATA_HOME/xoot/xoot.db`
(default `~/.local/share/xoot/xoot.db`); `--db PATH` on `xoot` and `xoot-mcp`
picks another file. A newly created directory gets mode 0700 and a new
database file 0600. On every open, a data directory, database or WAL/SHM file
that is a symlink, has another owner or any group/other bit set is refused,
never chmod-ed. The database never lives in this repository.

## Uninstall

```sh
uv tool uninstall xoot
claude mcp remove xoot                # if registered with Claude Code
claude plugin uninstall xoot          # if installed as the plugin
```

Remove the `xoot` entry from Claude Desktop's config too. The database is
kept; delete `~/.local/share/xoot/` (or your `--db` file) to remove it.

## Screenshots

Coming with the dashboard.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
