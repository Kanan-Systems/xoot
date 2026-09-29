# Workflow

Working with xoot's goal model, alone or across several clients. The terms
are defined in [Concepts](concepts.md).

## The loop

1. **Brief**: read the project with `brief_get` (or `xoot brief`): open
   goals with batch progress, what open backlog blocks, backlog per level,
   recent decisions and the workflow's state names.
2. **Plan**: create a goal with its batches and subtasks, in one
   `items_create_bulk` (previewed, then applied with its token) or item by
   item with `item_create`.
3. **Work**: move subtasks through the workflow with `item_update`, passing
   the version from your last read. Record decisions on the item they were
   made on.
4. **Capture**: the moment you find work outside the subtask at hand,
   `capture` it with `found_on` and a body saying why, and go back to the
   subtask. Check `backlog_list` first; never capture a duplicate.
5. **Clear the backlog**: cover an item as a subtask (`backlog_cover`),
   resolve it directly (`item_update` to its done state), or push it up a
   level (`backlog_push`).
6. **Completion**: batches and goals complete on their own. Every write
   result lists what it `completed`, `reopened` and what stays `blocked`.

## Completion and backlog rules

| Situation | What happens |
|---|---|
| Last open subtask of a batch closes, no open backlog on the batch | The batch moves to `done` (or `dropped` if every subtask was dropped); then its goal is evaluated the same way |
| Every subtask closed, but open backlog on the batch | Nothing changes; the write reports `blocked: [{key, open_backlog}]` |
| Every batch closed, but open backlog on the goal | The goal stays open and is reported blocked |
| A batch or goal has no children | It never completes |
| A subtask is created in, or reopened under, a done batch | The batch reopens, and a done goal above it |
| A backlog item is captured or pushed onto a done batch or goal | It reopens |
| A backlog item is covered, resolved or pushed away | Its old level may complete |

Backlog cascades upward: batch backlog can be pushed to its goal, goal
backlog to the project. A project-level item is covered into a named batch
of any goal, or resolved directly.

## Workflow states

The default workflow gives goals, batches and subtasks one state per
category (`open`, `active`, `blocked`, `awaiting_input`, `done`, `dropped`)
and backlog items `open`, `done` and `dropped`, all unrestricted. Every
kind needs defaults for `open`, `done` and `dropped`: the completion engine
uses them.

`xoot workflow export` writes the active workflow as TOML, and `xoot
workflow import FILE` replaces it, remapping items in removed states with
`--map KIND:OLD=NEW`. A file from xoot 0.2 that still uses the removed
`backlogged` category is refused with a message saying so.

## Decisions

Record a decision when a choice constrains later work: a design choice, a
scope cut, a convention. Put the reason in the body and record it on the
goal, batch or subtask it governs. Use `deferred` for a choice deliberately
postponed, and mark items that cannot move until it is made as awaiting it.

When a decision changes, record a new one that supersedes the old one (it
must be on the same goal) instead of rewriting it, so the history shows
what was decided when and why. Edit a decision in place only to correct or
clarify its text.

## Conflicts

Every update carries `expected_version` from your last read of the record.
If someone else changed it in between, the update is refused with the
fields and actors that changed it. Re-read the record; if the other change
touched the fields you are changing, ask the user which should win before
retrying.

## A planning chat plus a coding agent

A common split: plan in a chat client (Claude Desktop, or a browser through
paste mode) and build in Claude Code. Both work on the same goal at once.

- The planning chat creates the goal, its batches and subtasks, records the
  decisions, and writes the build prompt, naming the subtask keys.
- The coding agent works those subtasks, captures what it finds on the
  subtask it was on instead of fixing it out of scope, and marks what it
  finished done; the batch and goal complete by themselves.
- Back in the planning chat, the next brief shows the progress, what open
  backlog blocks, and the captures to triage.

## Paste round-trip tips

- Paste the brief fresh for each exchange: its versions go stale as soon
  as anything writes.
- Ask for at most one ```` ```xoot ```` block per reply.
- Copy the reply with the message's copy button, not the code block's.
- Read the plan before answering y: it names every record, what the block
  completes, reopens or leaves blocked, and flags POSSIBLE ENCODING DAMAGE.
- Paste the ```` ```xoot-receipt ```` block back into the chat so the next
  block uses current keys and versions.
