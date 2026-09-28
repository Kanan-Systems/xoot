# Concepts

The words xoot uses, what each one means, and the rules the database
enforces around it.

## Project

A project is one tracked body of work. It has a key prefix, a display name,
optional aliases and the directories it lives in. `xoot init --prefix P`
registers the working directory (or a given path) as a project; `xoot
project add-path` adds more directories.

A key prefix is 2-32 lowercase letters or digits, starting with a letter,
with no dashes: every key splits on its first dash, so `ab-12` can only be
item 12 of project `ab`. An alias may contain dashes (`my-app`) but must not
look like an item, decision or session key (`xoot-12`, `xoot-d3`, `ab-s1`).
Prefixes and aliases share one namespace, so every name finds exactly one
project.

## Items: goal, batch, subtask

Work is a tree of three kinds of item:

- **goal**: a top-level outcome. A goal has no parent.
- **batch**: a slice of a goal. A batch always has a goal as its parent.
- **subtask**: one piece of work. Its parent is a batch, or none at all.

A subtask with no parent is **unfiled**. Captured side items start unfiled
and can be moved under a batch later. The database itself rejects a batch
under a batch or a subtask under a goal.

Every item has a title (up to 200 characters), a body (up to 32 KiB), a
state and a version that goes up with each change.

## Session

A session is one sitting of work by one client. It starts with a title and
optional focus items (the items it means to work on), links every item it
touches, and ends with a close. Several sessions can be open at once; a
session start warns when a focus item is also held by another open session.

## Backlog

An item that is parked rather than worked on is **backlogged**. There are
two backlogs:

- **session backlog**: parked by a session's close, with that session
  named. The next session's start lists these items under `pending`, so
  work parked at a close is offered again for triage.
- **project backlog**: parked with no session attached.

Triage happens at the next session. When a session closes, items still
parked in the backlog of a session that had already closed before this one
started move to the project backlog. These are the **auto-backlog** moves:
the close preview lists them as warnings, and they are recorded as the
system's writes, not the closer's.

## Dispositions

Closing a session needs a disposition for every open item linked to it:

| Disposition | Effect |
|---|---|
| `carry_over` | Keeps the item's state; the next session picks it up. |
| `session_backlog` | Moves it to the default backlogged state, in this session's backlog. |
| `project_backlog` | Moves it to the default backlogged state, in the project backlog. |
| `dropped` | Moves it to the default dropped state. |

Done and dropped items need none. A close that leaves any item without a
disposition fails and names the missing keys.

## Capture

Capture records a side item the moment it appears, without derailing the
session: it creates an unfiled subtask parked in the current session's
backlog. Check the tree and the backlog first; one finding is one item.

## Decision

A decision is a recorded choice with its rationale: a title, a body that
explains why, and optionally the item it is scoped to. An item can also be
marked as awaiting a decision. Its status is one of:

- **locked**: in force.
- **deferred**: deliberately postponed.
- **superseded**: replaced by a newer decision. Recording a decision that
  supersedes another changes the older one's status in the same
  transaction. Superseded is terminal and only reached this way.

Title, body and status stay editable (except the status of a superseded
decision), and every change is kept in the history.

## Workflow states and categories

Each project names its own states, per item kind. Every state belongs to
exactly one of seven fixed categories, and xoot's rules (backlogs, session
close, tree filtering) reason only in categories:

`open`, `active`, `blocked`, `awaiting_input`, `done`, `dropped`,
`backlogged`.

`done` and `dropped` are terminal. The default workflow has one state per
category, named after it, with no transition restrictions. `xoot workflow
export` and `xoot workflow import` change it as a TOML file.

## Keys

- `<prefix>-<n>` for items. One counter per project is shared by goals,
  batches and subtasks, so a key never encodes the kind or the parent and
  survives a reparent unchanged.
- `<prefix>-D<n>` for decisions.
- `<prefix>-S<n>` for sessions.

Keys are never reused.

## History and redaction

Every write appends an event with the actor, the client, the session (if
any) and the before and after values of what changed. The event log is
append-only: the database refuses deletes and every update except a
redaction.

`xoot redact KEY FIELD` is the one sanctioned rewrite. Only the user can run
it, from the CLI. It clears a title, body, summary or project name to
`[redacted]`, removes that field's content from every event of the entity,
records a `redact` event that names the field but never the content, and
purges the old text from the database files. Key prefixes and aliases are
part of every key and cannot be redacted.

## Actors and clients

Every event records who wrote it and through which client.

| Actor | Meaning |
|---|---|
| `claude` | Claude, through an MCP client or paste mode. |
| `user` | The user, through the CLI. |
| `system` | xoot itself, as a consequence of another write (auto-backlog moves, workflow remaps). |

| Client | Where the write came from |
|---|---|
| `code` | An MCP client whose reported name contains `claude-code`. |
| `chat` | Any other MCP client. |
| `cli` | The `xoot` command. |
| `paste` | `xoot paste apply`, confirmed by the user at the terminal. |

The client name comes from what the MCP client reports at initialization. It
is unauthenticated: it labels the session and grants nothing.
