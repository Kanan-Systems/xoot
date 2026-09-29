// The drawer's history lines ("actor · client · date · change") and the
// completion state of a goal or batch, all as plain text.
import type { EventEntry, ItemDetail } from '../api/types.gen.ts';
import { when } from './display.ts';

function value(raw: unknown): string {
  if (raw === null || raw === undefined) {
    return 'none';
  }
  return typeof raw === 'string' ? raw : JSON.stringify(raw);
}

function change(event: EventEntry): string {
  if (event.action === 'create') {
    return 'created';
  }
  if (event.action === 'redact') {
    return 'redacted';
  }
  const parts = event.changed.map((field) => {
    const before = event.before ?? {};
    const after = event.after ?? {};
    if (!(field in before) && !(field in after)) {
      return `${field} changed`;
    }
    return `${field}: ${value(before[field])} → ${value(after[field])}`;
  });
  const text = parts.length > 0 ? parts.join('; ') : event.action;
  return event.redacted ? `${text} (redacted)` : text;
}

export function historyLine(event: EventEntry): string {
  return [event.actor_kind, event.client, when(event.created_at), change(event)].join(
    ' · ',
  );
}

// Events come newest first; the latest one that set the state tells who
// closed the item.
function lastStateChange(events: readonly EventEntry[]): EventEntry | undefined {
  return events.find(
    (event) =>
      event.after !== null && 'state' in event.after && event.action !== 'create',
  );
}

export function completionState(
  item: ItemDetail,
  events: readonly EventEntry[],
  openBacklog: number | undefined,
): string | null {
  if (item.kind !== 'goal' && item.kind !== 'batch') {
    return null;
  }
  const children = item.kind === 'goal' ? 'batches' : 'subtasks';
  if (openBacklog !== undefined) {
    return `Blocked by ${String(openBacklog)} open backlog: all ${children} done.`;
  }
  if (item.category === 'done' || item.category === 'dropped') {
    const closed = lastStateChange(events);
    if (closed === undefined) {
      return item.category === 'done' ? 'Done.' : 'Dropped.';
    }
    const verb = item.category === 'done' ? 'Completed' : 'Dropped';
    const how =
      closed.actor_kind === 'system' ? 'automatically' : `by ${closed.actor_kind}`;
    return `${verb} ${how} · ${when(closed.created_at)}`;
  }
  return `Completes automatically once all ${children} are done or dropped and no backlog is open.`;
}
