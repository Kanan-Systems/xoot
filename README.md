# xoot

Local-only tracker for goals, batches and subtasks across Claude sessions.

## Status

Pre-alpha. The storage layer and domain services exist, but there is no CLI,
MCP server or entry point yet, so nothing is usable end to end.

## Data

State lives in a local SQLite database at `$XDG_DATA_HOME/xoot/xoot.db`
(default `~/.local/share/xoot/xoot.db`). A newly created directory gets mode
0700 and a new database file 0600; existing ones are left as they are. The
database never lives in this repository.

## Development

uv has no config-file key for the venv path, so export the variable first:

```sh
export UV_PROJECT_ENVIRONMENT=env
uv sync --locked               # creates or reuses env/ from uv.lock
env/bin/pre-commit install     # the hook then runs pre-commit from env/
```

## License

MIT. See [LICENSE](LICENSE).
