# Concepts

The words xoot uses, what each one means, and the rules the database
enforces around it.

## Project

A project is one tracked body of work. It has a key prefix, a display name,
optional aliases and the directories it lives in. `xoot init --prefix P`
registers the working directory (or a given path) as a project; `xoot
project add-path` adds more directories.

A key prefix is 2-32 lowercase letters or digits, starting with a letter,
with no dashes. An alias may contain dashes (`my-app`) but must not look
like a key segment (`goal-12`, `backlog-3`). Prefixes and aliases share one
namespace, so every name finds exactly one project.

## Items: goal, batch, subtask, backlog

Work is a tree of four kinds of item:

- **goal**: a top-level outcome. A goal sits on the project.
- **batch**: a slice of a goal. Its parent is always a goal.
- **subtask**: one piece of work. Its parent is always a batch.
- **backlog**: open work found along the way. It sits on a batch, on a
  goal, or on the project (the project backlog).

The database itself rejects any other parent. Every item has a title (up to
200 characters), a body (up to 32 KiB), a state and a version that goes up
with each change.

Items belong to goals, not to conversations: any number of conversations,
chats and Claude Code agents may work on the same goal at once. Every write
records its actor and client (see below).

## Keys

Keys are nested paths, unique within one project. Each number is allocated
by the item's parent (the project, for goals and the project backlog), from
a counter that only grows, so a key is never handed out twice.

| Item | Key shape | Example |
|---|---|---|
| goal | `goal-<n>` | `goal-1` |
| batch | `goal-<n>/batch-<m>` | `goal-1/batch-2` |
| subtask | `goal-<n>/batch-<m>/subtask-<k>` | `goal-1/batch-2/subtask-3` |
| project backlog | `backlog-<k>` | `backlog-4` |
| goal backlog | `goal-<n>/backlog-<k>` | `goal-1/backlog-5` |
| batch backlog | `goal-<n>/batch-<m>/backlog-<k>` | `goal-1/batch-2/backlog-6` |
| decision | `<goal, batch or subtask key>/decision-<j>` | `goal-1/batch-2/decision-1` |

Any key may be qualified with its project: `<prefix>:<key>`, e.g.
`xoot:goal-1/batch-2`. A call's project comes from the explicit project
argument, then the qualifier of its keys, then the client's roots, then the
working directory (Claude Code). Chat clients pass the project.

When an item moves (a reparent, or a backlog push), it takes the next
number of its new parent and every key below it changes with it. Each old
key is recorded as an **alias** and keeps resolving to the item forever. A
decision's key follows its owner's current key.

## Completion

Goals and batches complete on their own; nobody sets them done by hand.

- A **batch** completes when every subtask is done or dropped **and** no
  open backlog item sits on the batch. It moves to its default `done`
  state, or to its default `dropped` state when every subtask was dropped.
- A **goal** completes the same way: every batch done or dropped, and no
  open backlog on the goal itself.
- A batch or goal with no children never completes.
- Open backlog **blocks** completion. While every child is closed but open
  backlog remains, nothing changes and the write reports the item as
  `blocked` with its open backlog count; the brief lists it too.
- A closed batch or goal **reopens** (back to its default `open` state)
  when it gains open work: a new or reopened subtask, a new batch, or new
  or pushed-in open backlog.

These writes are recorded as the `system` actor in the same transaction.
Every write result lists the keys it `completed` and `reopened`, and what
stays `blocked`.

## Backlog

A backlog item is work found along the way that is not yet a subtask. It
is closed in one of three ways, each of which counts toward completion:

- **cover**: `backlog_cover` turns it into a subtask (same title and body)
  and closes it. The subtask records the item as its `origin`, the item
  records the subtask as `covered_by`. It lands in the item's own batch,
  or in a named batch: of the same goal for an item on a goal, of any goal
  for a project-level item.
- **resolve**: `item_update` to its done (or dropped) state, when the work
  is done without a subtask.
- **push**: `backlog_push` moves it one level up: batch to goal, goal to
  project. It is two-phase (preview, then apply with a token). The project
  is the top.

Backlog **cascades upward**: batch, then goal, then project. Pushing an item
off a batch can let that batch complete; pushing it onto a closed goal
reopens the goal.

## Capture

`capture` records a backlog item the moment it appears. `found_on` is the
item it was found on (any kind) and the body says why. It lands:

| found_on | Lands on |
|---|---|
| a subtask | the subtask's batch |
| a batch | that batch |
| a goal | that goal |
| a backlog item | the same level as that item (the project for a project-level one) |

A capture reopens a done batch or goal, since open backlog now sits on it.
Check `backlog_list` first: one finding is one item.

## Decision

A decision is a recorded choice with its rationale: a title and a body that
explains why. It belongs to the goal, batch or subtask it was made on, which
numbers it. An item can also be marked as awaiting a decision. Its status is
one of:

- **locked**: in force.
- **deferred**: deliberately postponed.
- **superseded**: replaced by a newer decision of the same goal. Recording
  a decision that supersedes another changes the older one's status in the
  same transaction. A decision is superseded at most once, and superseded
  is terminal.

Title, body and status stay editable (except the status of a superseded
decision), and every change is kept in the history.

## Workflow states and categories

Each project names its own states, per item kind. Every state belongs to
exactly one of six fixed categories, and xoot's rules (completion, backlog
counts, tree filtering) reason only in categories:

`open`, `active`, `blocked`, `awaiting_input`, `done`, `dropped`.

`done` and `dropped` are terminal. Every kind needs a default state for
`open`, `done` and `dropped`. See [Workflow](workflow.md).

## History and redaction

Every write appends an event with the actor, the client and the before and
after values of what changed. The event log is append-only: the database
refuses deletes and every update except a redaction.

`xoot redact KEY FIELD` is the one sanctioned rewrite. Only the user can run
it, from the CLI. It clears an item or decision title or body, or a project
name, to `[redacted]`, removes that field's content from every event of the
entity, records a `redact` event that names the field but never the
content, and purges the old text from the database files.

## Actors and clients

Every event records who wrote it and through which client.

| Actor | Meaning |
|---|---|
| `claude` | Claude, through an MCP client or paste mode. |
| `user` | The user, through the CLI or the dashboard. |
| `system` | xoot itself, as a consequence of another write (completion, reopening, workflow remaps). |

| Client | Where the write came from |
|---|---|
| `code` | An MCP client whose reported name contains `claude-code`. |
| `chat` | Any other MCP client. |
| `cli` | The `xoot` command. |
| `dashboard` | `xoot dashboard`, in the browser (actor `user`). |
| `paste` | `xoot paste apply`, confirmed by the user at the terminal. |

The MCP client is mapped per call from what it reported at initialization.
The name is unauthenticated: it labels the write and grants nothing.
