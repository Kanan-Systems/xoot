# xoot

Local-only tracker for goals, batches and subtasks across Claude sessions.

## Status

Pre-alpha. Nothing is usable yet; the package contains only a version string.

## Development

uv has no config-file key for the venv path, so export the variable first:

```sh
export UV_PROJECT_ENVIRONMENT=env
uv sync --locked               # creates or reuses env/ from uv.lock
env/bin/pre-commit install     # the hook then runs pre-commit from env/
```

## License

MIT. See [LICENSE](LICENSE).
