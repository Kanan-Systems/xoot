# Contributing

## Setup

The virtual environment lives in `env/`, not uv's default `.venv/`. uv has
no config-file key for the venv path, so export the variable first, in every
shell you run uv from:

```sh
export UV_PROJECT_ENVIRONMENT=env
uv sync --locked               # creates or reuses env/ from uv.lock
env/bin/pre-commit install     # optional: run the gates on every commit
```

Run tools from `env/bin/` (or with `uv run` while the variable is exported).

## Gates

`.pre-commit-config.yaml` is the single source of truth for the gates:
isort, black, pylint (which must score 10) and pytest. Run them all as the
final check before any change is proposed:

```sh
env/bin/pre-commit run --all-files
```

CI (`.github/workflows/backend-gates.yml`) runs the same tools from the
locked environment. Its pytest step also writes a coverage report to the job
summary. Coverage is a report only: there is no threshold, and it gates
nothing.

Every change needs tests: new behaviour, bug fixes (a regression test) and
failure paths.

## Migrations are frozen

The schema lives in `src/xoot/store/migrations/`. A migration that has been
committed is never edited. Every schema change is a new migration file, so
every existing database upgrades along the same path.

## Release checklist

Tags and commits are the maintainer's.

1. Bump the version in `pyproject.toml` and in
   `plugin/.claude-plugin/plugin.json`; they must match (a test checks).
2. `uv lock`, so the lockfile records the new version.
3. Run the gates, then commit.
4. Tag the commit `vX.Y.Z`, matching the version.

## No telemetry

xoot adds no telemetry, analytics or other network calls. A change that
would send anything off the machine will not be accepted.
