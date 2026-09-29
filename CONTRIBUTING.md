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

### Frontend (the dashboard)

The dashboard's sources live in `dashboard/`. Node is pinned in
`dashboard/.nvmrc` and every package version is exact in `package-lock.json`:

```sh
cd dashboard
nvm use          # the version in .nvmrc
npm ci           # installs exactly what package-lock.json records
```

Users never need Node: the built bundle is committed in
`src/xoot/dashboard/static/`.

## Gates

`.pre-commit-config.yaml` is the single source of truth for the gates:
isort, black, pylint (which must score 10) and pytest, then, for changes
under `dashboard/`, eslint, prettier --check, tsc --noEmit and vitest (run
through `npm --prefix dashboard run ...`, so `npm ci` must have run). Run
them all as the final check before any change is proposed:

```sh
env/bin/pre-commit run --all-files
```

CI (`.github/workflows/backend-gates.yml`) runs the same tools from the
locked environment. Its pytest step also writes a coverage report to the job
summary. Coverage is a report only: there is no threshold, and it gates
nothing.

Every change needs tests: new behaviour, bug fixes (a regression test) and
failure paths.

### Dashboard: schema, types and bundle

The API's JSON Schema, the TypeScript types and the bundle are all
committed, and each is checked for drift:

1. After changing a dashboard response model, export the schema:
   `env/bin/python -m xoot.dashboard.export_schema` (a pytest test compares
   `dashboard/src/api/schema.json` with a fresh export).
2. Regenerate the types: `npm --prefix dashboard run gen:types` (a vitest
   test and CI compare `dashboard/src/api/types.gen.ts`).
3. Rebuild the bundle before committing any frontend change:
   `npm --prefix dashboard run build`. CI (`frontend-gates.yml`) rebuilds it
   and fails on any difference from the committed
   `src/xoot/dashboard/static/`.

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
