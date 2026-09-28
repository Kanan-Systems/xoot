# Workflow

Patterns for working with xoot across sessions and clients. The terms are
defined in [Concepts](concepts.md).

## The session loop

1. **Brief**: read the project with `brief_get` (or `xoot brief`): open
   sessions, items in flight, pending backlog and recent decisions.
2. **Start**: `session_start` with a title and the focus items. Read its
   `pending` list (items earlier sessions parked) and its warnings (focus
   items another open session holds).
3. **Work**: move items through the workflow with `item_update`, record
   decisions as they are made.
4. **Capture**: the moment a side item appears, `capture` it and go back to
   the focus.
5. **Close**: `session_close` with a disposition for every open linked item.
   Read the preview, including every auto-backlog warning, before
   confirming with the token.
6. **Triage**: the next session's start lists what this one parked. Refile,
   pick up or drop those items in that session; whatever is still parked
   when it closes moves to the project backlog.

## Focus items

Name the items a session works on as its focus at the start. Focus keeps a
session small and makes its close quick: each focus item gets a disposition,
and a warning shows when another open session holds the same item. Prefer a
few subtasks over a whole goal.

## Decisions

Record a decision when a choice constrains later work, especially one a
future session could otherwise re-open: a design choice, a scope cut, a
convention. Put the reason in the body and scope it to the item it governs.
Use `deferred` for a choice deliberately postponed, and mark items that
cannot move until it is made as awaiting it.

When a decision changes, record a new one that supersedes the old one
instead of rewriting it, so the history shows what was decided when and why.
Edit a decision in place only to correct or clarify its text.

## Conflicts

Every update carries `expected_version` from your last read of the record.
If someone else changed it in between, the update is refused. Re-read the
record; if the other change touched the fields you are changing, ask the
user which should win before retrying.

## A planning chat plus a coding agent

A common split: plan in a chat client (Claude Desktop, or a browser through
paste mode) and build in Claude Code.

- The planning chat creates goals, batches and subtasks, records the
  decisions, and writes the build prompt, naming the focus item keys.
- The coding agent starts its own session with those keys as focus,
  captures what it finds instead of fixing it out of scope, marks what it
  completed, and closes.
- Back in the planning chat, the next brief shows the results, the new
  captures and the backlog to triage.

Both sessions can be open at once; the focus warnings show the overlap.

## Paste round-trip tips

- Paste the brief fresh for each exchange: its versions go stale as soon
  as anything writes.
- Ask for at most one ```` ```xoot ```` block per reply.
- Copy the reply with the message's copy button, not the code block's.
- Read the titles in the plan before answering y: a code page can damage
  text silently, and the plan flags POSSIBLE ENCODING DAMAGE.
- Paste the ```` ```xoot-receipt ```` block back into the chat so the next
  block uses current versions.
