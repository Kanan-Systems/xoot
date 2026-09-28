# xoot

Local-only tracker for goals, batches and subtasks across Claude sessions.

## Status

Pre-alpha. `xoot-mcp` (or `python -m xoot.server`) serves the tracker to MCP
clients over stdio. It opens the database below, or the file given with
`--db PATH`, and logs the path it uses once to stderr. Tools take public keys
(`xoot-12`, `xoot-D3`, `xoot-S4`); bulk creates, subtree drops and moves, and
session closes are previewed first and applied with a single-use token.

## CLI

`xoot` (or `python -m xoot.cli`) is the user's own entry point. Every write
is recorded as the user, client `cli`, outside any session, except paste
mode's (below).

```sh
xoot init [PATH] --prefix xoot [--name N] [--alias A]...
xoot project list | show | add-alias A | remove-alias A | add-path P | remove-path P
xoot brief | tree [--root KEY] [--depth N] [--all]
xoot workflow export [-o FILE] | import FILE [--map kind:old=new]... [--yes]
xoot redact KEY FIELD [--yes]      # KEY: item, decision or session key, or a prefix
xoot paste brief | apply SOURCE [--yes]
xoot db stats | vacuum
```

A key prefix is 2-32 lowercase letters or digits, starting with a letter,
with no dashes: every key splits on its first dash, so `ab-12` can only be
item 12 of project `ab`. An alias may contain dashes (`my-app`, `a-b-c`) but
must not look like an item, decision or session key (`xoot-12`, `xoot-d3`,
`ab-s1`).

`--project NAME` takes an alias or a key prefix; without it the project is
the one whose path contains the working directory. `--db PATH` and `--json`
work before or after the command; `--json` prints the same models the MCP
tools return. Results go to stdout, errors, warnings and prompts to stderr.
`workflow import`, `redact`, `remove-alias` and `remove-path` show what will
change and ask y/N; without a terminal they need `--yes`. Exit codes: 0 ok,
1 refused, 2 usage, 3 database unavailable (unsafe path, open failure, busy,
or a redaction whose purge did not complete: close clients and redo it).

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
(default `~/.local/share/xoot/xoot.db`). A newly created directory gets mode
0700 and a new database file 0600. On every open, a data directory, database
or WAL/SHM file that is a symlink, has another owner or any group/other bit
set is refused, never chmod-ed. The database never lives in this repository.

## Development

uv has no config-file key for the venv path, so export the variable first:

```sh
export UV_PROJECT_ENVIRONMENT=env
uv sync --locked               # creates or reuses env/ from uv.lock
env/bin/pre-commit install     # the hook then runs pre-commit from env/
```

## License

MIT. See [LICENSE](LICENSE).
