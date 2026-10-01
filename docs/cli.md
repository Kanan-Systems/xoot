# CLI reference

`xoot` is the user's own entry point (`python -m xoot.cli` runs the same
thing). Every write it makes is recorded as actor `user`, client `cli`,
except `xoot paste apply`, which records `claude`, client `paste`.

The CLI registers and renames projects, shows the tracker, and maintains
the database. It cannot create items, and it cannot change an item's
state or parent. Do that from a chat (MCP), the dashboard, or paste mode.
`xoot redact` only clears a title or body, and `xoot workflow import` only
moves items out of states it removes.

## Global options

| Option | Meaning |
|---|---|
| `--db PATH` | Database file (default: `$XDG_DATA_HOME/xoot/xoot.db`, else `~/.local/share/xoot/xoot.db`) |
| `--json` | Print results as JSON |
| `--version` | Print `xoot <version>` and exit (top level only) |
| `-h`, `--help` | Help for the command or action |

### Where the global options go

`--db` and `--json` go **before the command** or **after the action**,
never between a command group (`project`, `workflow`, `paste`, `db`) and its
action:

```sh
xoot --json project list          # works
xoot project list --json          # works
xoot project --json list          # usage error, exit 2
```

The last one prints `xoot: error: unrecognized arguments: --json`. Commands
without an action (`init`, `brief`, `tree`, `redact`, `dashboard`) take the
options before or after the command.

### Project selection

Commands with `--project NAME` take an alias or a key prefix. Without it,
the project is the one with a registered path that contains the working
directory. When none does, the command fails with `error:
ProjectResolutionError: project not resolved; one of: ...`, listing the
names it knows. A key can also carry its project, as `<prefix>:<key>`
(`xoot tree --root csv:goal-1`).

### Confirmation and `--yes`

`--yes` is not a global option. Commands that remove or rewrite data show
the change and ask on the terminal. Without one, they stop (exit 1) with
the message below, unless `--yes` is given:

| Command | Asks | Without a terminal and without `--yes` |
|---|---|---|
| `project remove-alias`, `project remove-path`, `project rename` | `Proceed? [y/N]` on stdin | `error: ConfirmationError: stdin is not a terminal; pass --yes to confirm` |
| `workflow import` (only when the workflow changes) | `Proceed? [y/N]` on stdin | `error: ConfirmationError: stdin is not a terminal; pass --yes to confirm` |
| `redact` | `Proceed? [y/N]` on stdin | `error: ConfirmationError: stdin is not a terminal; pass --yes to confirm` |
| `paste apply` | `Apply? [y/N]` on the controlling terminal (`/dev/tty`), since stdin may hold the paste | `error: ConfirmationError: no controlling terminal to confirm on; pass --yes to confirm` (the plan is still printed) |

No other command takes `--yes`.

Declining a prompt (any answer but `y` or `yes`) writes nothing and exits 1,
the code of any refusal, with `error: ConfirmationError: aborted; nothing was
written`.

### Output and exit codes

Results go to stdout. Errors, warnings, plans and prompts go to stderr.

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Refused: invalid input or a rule the tracker enforces |
| 2 | Usage error (as argparse reports it) |
| 3 | The database could not be used: an unsafe path, a failed open, a busy database, stored data this version cannot read, or a redaction whose purge did not complete; also `xoot dashboard` when its port cannot be bound |

Every command opens the database first, and creates and migrates it if
needed, even one that only reads.

## Commands

### `xoot init [PATH]`

Register a project for a directory (default: the working one).

| Flag | Meaning |
|---|---|
| `--prefix PREFIX` | Required. The key prefix: 2-32 lowercase letters or digits, starting with a letter, no dashes. It never changes. |
| `--name NAME` | Display name (default: the prefix) |
| `--alias ALIAS` | An alias; may be repeated. May contain dashes, but must not look like a key segment (`goal-12`, `backlog-3`). |

```sh
$ xoot init /home/you/code/csvtool --prefix csv --name "CSV tool" --alias csv-tool
project: csv
name: CSV tool
aliases: csv-tool
paths: /home/you/code/csvtool
```

A prefix such as `bad-x` is refused with `error: ValidationError:
key_prefix: a key prefix is 2–32 lowercase letters or digits, starting with
a letter; no dashes` (exit 1).

### `xoot project ACTION`

| Action | Purpose | Flags |
|---|---|---|
| `list` | List every project and the database in use | — |
| `show` | Show one project | `--project` |
| `add-alias ALIAS` | Add an alias | `--project` |
| `remove-alias ALIAS` | Remove an alias | `--project`, `--yes` |
| `add-path PATH` | Add a directory | `--project` |
| `remove-path PATH` | Remove a directory | `--project`, `--yes` |
| `rename [PROJECT]` | Change the display name and/or add an alias; never the prefix. Name the project once: as `PROJECT` or with `--project` | `--project`, `--name NAME`, `--alias ALIAS` (one), `--yes` |

```sh
$ xoot project list
database: /home/you/.local/share/xoot/xoot.db
PREFIX  NAME      ALIASES   PATHS
csv     CSV tool  csv-tool  /home/you/code/csvtool

$ xoot project rename --project csv --name "CSV toolkit" --alias csv-toolkit --yes
project: csv
name: CSV toolkit
aliases: csv-tool, csv-toolkit
paths: /home/you/code/csvtool
```

`xoot project rename csv --name "CSV toolkit"` does the same. Naming the
project both ways with different names, or not at all, is a usage error
(exit 2) before the database is opened: `xoot project rename: error: name
the project once: PROJECT or --project`.

Aliases are kept when a project's name changes or is redacted; remove one
that spells the old name with `xoot project remove-alias ALIAS --project
PREFIX`.

### `xoot brief`

Summarize a project: counts per category, open goals with batch progress,
active and awaiting-input items, what open backlog blocks, open backlog per
level, recent decisions and the workflow. Flag: `--project`.

### `xoot tree`

Show the item tree. Done and dropped items are hidden unless `--all` is
given.

| Flag | Meaning |
|---|---|
| `--project NAME` | Project selection |
| `--root KEY` | Item key to start from (or `<prefix>:<key>`) |
| `--depth N` | Levels below the roots, 0-8 (default: 3) |
| `--all` | Include done and dropped items |

```sh
$ xoot tree --project csv --all
goal-1                        goal     open (open)      CSV export
  goal-1/batch-1              batch    open (open)      Writer
    goal-1/batch-1/subtask-1  subtask  active (active)  Quote cells
    goal-1/batch-1/backlog-1  backlog  open (open)      Handle BOM
```

The state column shows `state (category)`. If `--depth` or the item limit
hides items, stderr says `warning: the tree was truncated by --depth or the
item limit`.

### `xoot backlog`

List backlog items, read-only, grouped by what they sit on: the project
backlog first, then each goal's and batch's own, as the MCP tool
`backlog_list` orders them, at most 100 (a warning on stderr says when more
were hidden). Done and dropped items are hidden unless `--all` is given.

| Flag | Meaning |
|---|---|
| `--project NAME` | Project selection |
| `--at KEY` | Only the backlog on this goal or batch (or `<prefix>:<key>`) |
| `--all` | Include done and dropped backlog items |

```text
$ xoot backlog --project csv --all
on goal-1 (goal backlog)
  goal-1/backlog-1  open (open)  Document the format  (found on goal-1)
  goal-1/backlog-2  dropped (dropped)  Old idea  (found on goal-1)
on goal-1/batch-1 (batch backlog)
  goal-1/batch-1/backlog-1  open (open)  Handle BOM  (found on goal-1/batch-1/subtask-1)
```

With `--json` the output has the shape `backlog_list` returns. An `--at`
key that names nothing is `error: NotFoundError: ...` (exit 1); an empty
list prints `(no backlog)`.

### `xoot workflow ACTION`

| Action | Purpose | Flags |
|---|---|---|
| `export` | Print the active workflow as TOML, or write it to a file | `--project`, `-o/--output FILE` |
| `import FILE` | Replace the workflow with a TOML file (at most 64 KiB) | `--project`, `--map KIND:OLD=NEW` (may be repeated), `--yes` |

`--map` moves items of `KIND` in a removed state `OLD` to `NEW`. See
[Workflow](workflow.md#workflow-states).

```sh
$ xoot workflow export --project csv -o workflow.toml
wrote csv workflow version 1 to /home/you/code/csvtool/workflow.toml
$ xoot workflow import workflow.toml --project csv --yes
no changes: csv workflow is still version 1
```

### `xoot redact KEY FIELD`

Clear a text field to `[redacted]`, remove it from the history of that
record, and purge the old text from the database files. `KEY` is an item
or decision key (optionally `<prefix>:<key>`), or a key prefix alone for the
project name. `FIELD` is `title`, `body` or `name`. Flags: `--project`,
`--yes`. It cannot be undone.

```text
$ xoot redact goal-1/batch-1/backlog-1 body --project csv
redact the body of item goal-1/batch-1/backlog-1
the record and its history are rewritten; this cannot be undone
Proceed? [y/N] y
redacted body of item goal-1/batch-1/backlog-1, now version 2; 1 event rewritten
```

Redacting a project name keeps its aliases. A warning on stderr lists each
alias that equals the old or the new name as a slug (every alias when none
does), with the command to remove it; nothing is removed for you:

```text
$ xoot redact csv name --yes
redacted name of project csv; 2 events rewritten
warning: Aliases are kept when a project's name changes or is redacted; remove one that spells the old name with `xoot project remove-alias ALIAS --project PREFIX`.
warning: alias csv-toolkit: xoot project remove-alias csv-toolkit --project csv
```

### `xoot paste ACTION`

| Action | Purpose | Flags |
|---|---|---|
| `brief` | Print the markdown brief to paste into a chat (at most 16 KiB) | `--project` |
| `apply SOURCE` | Preview, confirm and apply one `xoot` block from a chat reply. `SOURCE` is a file, or `-` for stdin; at most 256 KiB | `--yes` |

The block names its own project, so `apply` takes no `--project`. See
[Claude in the browser](../README.md#claude-in-the-browser-paste-mode).

### `xoot db ACTION`

| Action | Purpose |
|---|---|
| `stats` | Page counts, file sizes, schema version and row counts |
| `vacuum` | Rebuild the file without free pages and truncate the WAL; asks nothing |

```sh
$ xoot db stats
database: /home/you/.local/share/xoot/xoot.db
schema version: 3 (latest known: 3)
db bytes: 167936
wal bytes: 0
pages: 41
free pages: 0

TABLE          ROWS
confirm_token  0
decision       0
event          12
item           4
item_alias     0
project        1
project_alias  2
project_path   1
workflow       1
```

### `xoot dashboard`

Serve the web dashboard on 127.0.0.1 in the foreground until Ctrl+C.

| Flag | Meaning |
|---|---|
| `--port N` | TCP port, 1-65535 (default: 7373) |
| `--open` | Also open the URL in a browser (`wslview` under WSL) |

See [Dashboard](../README.md#dashboard).

## `xoot-mcp`

The MCP server, started by the client, never by hand. It speaks MCP over
stdio and takes `--db PATH`, `--version` and `--help` only. It logs the
database path it uses to stderr once at start. An unsafe database path is
refused at start, with the line and exit code (3) `xoot dashboard` gives,
before anything is served or created:

```text
$ xoot-mcp --db /home/you/shared/xoot.db
error: UnsafePathError: refusing to open /home/you/shared: it grants group or other permissions (mode 0750)
```
