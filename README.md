# xoot

Local-only tracker for goals, batches and subtasks across Claude sessions.

## Status

Pre-alpha. `xoot-mcp` (or `python -m xoot.server`) serves the tracker to MCP
clients over stdio. It opens the database below, or the file given with
`--db PATH`, and logs the path it uses once to stderr. Tools take public keys
(`xoot-12`, `xoot-D3`, `xoot-S4`); bulk creates, subtree drops and moves, and
session closes are previewed first and applied with a single-use token.

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
