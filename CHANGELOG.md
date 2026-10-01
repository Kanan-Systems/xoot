# Changelog

All notable changes to xoot. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Every release adds its entry here.

## [1.0.0] - 2026-10-01

The first public release.

### Added

- `xoot backlog`: the open backlog from the terminal, grouped like the MCP
  `backlog_list`, with `--at KEY`, `--all` for closed items too, and `--json`.
- `xoot project rename --project P`, as an alternative to the positional
  project.
- After `xoot redact <prefix> name`, a warning lists the aliases that still
  spell the old or new name, with the command to remove each one. Aliases
  are never removed automatically.
- Third-party notices (`THIRD_PARTY_NOTICES.md`) shipped inside the package,
  generated offline from the lockfiles by `scripts/gen_notices.py`.
- This changelog, and a test that keeps the version in step across
  `pyproject.toml`, the plugin manifest, this file and the README.

### Changed

- `xoot-mcp` refuses an unsafe database path at startup, with the same
  message as the dashboard, instead of failing on each tool call.
- A project rename refused in the dashboard names the field (`name` or
  `alias`) instead of `*`.
- Dashboard: when a move's plan changes before you confirm it, the second
  prompt says what changed, by title. The drawer history drops
  `version: 1 -> 2` lines and names a move's target when it is known.
- Documentation: supported platforms (Linux and WSL tested, macOS untested)
  and what the installer's hash pins do and do not enforce.

### Removed

- Unused code: `utils.keys.qualify()` and the dashboard's `lib/plan.ts`.

## [0.4.1] - 2026-10-01

### Fixed

- Dashboard: a collapsed goal or batch accepts a drop again; nodes hidden
  under a collapsed parent, or folded away as done, are still not targets.
- A server left running across an upgrade now refuses the newer database
  (`database schema version N is newer than supported M`). The supported
  version is a constant in the code, not the migration files on disk.
- Stored data that cannot be read (for example an event from a newer
  client) is reported as `StoredDataError`, naming the table, row, field
  and value and suggesting a restart, instead of "invalid arguments".

### Added

- Dashboard URLs accept a project alias as well as the key prefix.
- README: how to find and stop servers left running after an upgrade.

## [0.4.0] - 2026-10-01

### Added

- Dashboard writes: create, edit, move, capture, cover, push and decide
  from the browser, with the same two-phase confirmation as the tools.
- Moving a batch or subtask by dragging it onto a new parent in the tree.
- A drop lands on the node under the pointer, or else the one the dragged
  node covers most.

### Changed

- The dashboard refreshes live and groups the backlog and decisions.

## [0.3.1] - 2026-09-30

### Added

- Collapsing goals and batches in the tree, remembered per project.
- `xoot project rename`.

### Changed

- Tree and backlog keep the natural order of the keys.

## [0.3.0] - 2026-09-29

### Changed

- A goal-centric model replaces sessions: goals hold batches, batches hold
  subtasks, and backlog and decisions sit on any of them. Work is no longer
  tied to one conversation.
- The dashboard shows the goal tree, the backlog and the decisions.

### Removed

- Databases from xoot 0.2 or earlier are refused and cannot be upgraded.

## [0.2.0] - 2026-09-29

### Added

- A read-only dashboard (`xoot dashboard`): the item tree, backlog and
  decisions, with live refresh, a legend and help per tab.

## [0.1.0] - 2026-09-28

### Added

- The `xoot-mcp` stdio server with keyed tools and two-phase confirm
  tokens for larger changes.
- The `xoot` CLI: projects, aliases and paths, workflows as TOML, database
  stats and vacuum, and redaction.
- Paste mode for Claude in the browser (`xoot paste brief`,
  `xoot paste apply`), with a warning on likely code-page damage.
- `install.sh` and the Claude Code plugin.
- A local SQLite store with private file permissions and secure delete.

[1.0.0]: https://github.com/Kanan-Systems/xoot/compare/v0.4.0...v1.0.0
[0.4.1]: https://github.com/Kanan-Systems/xoot/compare/v0.4.0...135331c
[0.4.0]: https://github.com/Kanan-Systems/xoot/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/Kanan-Systems/xoot/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/Kanan-Systems/xoot/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Kanan-Systems/xoot/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Kanan-Systems/xoot/releases/tag/v0.1.0
