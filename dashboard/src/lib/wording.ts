// Plain-language text for push, move and drop: what will happen and what
// did, with item kinds and titles from the tree instead of raw fields. Each
// function returns null when a title it needs is unknown, so the caller
// falls back to the server's own text.
import type { ChangeEntry, SubtreeOutput } from '../api/types.gen.ts';
import type { Titles } from './titles.ts';

type Kind = 'goal' | 'batch' | 'subtask' | 'backlog';

const NOUN: Record<Kind, [string, string]> = {
  goal: ['goal', 'goals'],
  batch: ['batch', 'batches'],
  subtask: ['subtask', 'subtasks'],
  backlog: ['backlog item', 'backlog items'],
};

const ORDER: readonly Kind[] = ['goal', 'batch', 'subtask', 'backlog'];

// The kind a key names, from its last segment.
export function kindOf(key: string): Kind | null {
  const kind = (key.split('/').pop() ?? '').replace(/-\d+$/, '');
  return ORDER.find((known) => known === kind) ?? null;
}

export function parentOf(key: string): string | null {
  const parts = key.split('/');
  return parts.length > 1 ? parts.slice(0, -1).join('/') : null;
}

// "batch 'Writer'", or null when the kind or title is unknown.
export function named(key: string, titles: Titles): string | null {
  const kind = kindOf(key);
  const title = titles.get(key);
  return kind === null || title === undefined ? null : `${NOUN[kind][0]} '${title}'`;
}

// A parent as a place: a batch also names its goal, for context.
function place(key: string | null, titles: Titles): string | null {
  if (key === null) {
    return 'the project';
  }
  const own = named(key, titles);
  const goal = kindOf(key) === 'batch' ? parentOf(key) : null;
  if (own === null || goal === null) {
    return own;
  }
  const goalTitle = titles.get(goal);
  return goalTitle === undefined ? own : `${own} (goal '${goalTitle}')`;
}

function counted(count: number, kind: Kind): string {
  return `${String(count)} ${NOUN[kind][count === 1 ? 0 : 1]}`;
}

// "2 subtasks and 1 backlog item", or '' for none.
export function countsText(counts: Partial<Record<Kind, number>>): string {
  const parts = ORDER.flatMap((kind) => {
    const count = counts[kind] ?? 0;
    return count > 0 ? [counted(count, kind)] : [];
  });
  if (parts.length <= 1) {
    return parts.join('');
  }
  return `${parts.slice(0, -1).join(', ')} and ${parts.at(-1) ?? ''}`;
}

// What else a plan touches besides its root, by kind.
function others(
  changes: readonly ChangeEntry[],
  root: string,
): Partial<Record<Kind, number>> {
  const counts: Partial<Record<Kind, number>> = {};
  for (const change of changes) {
    const kind = kindOf(change.key);
    if (change.key !== root && change.before.key !== root && kind !== null) {
      counts[kind] = (counts[kind] ?? 0) + 1;
    }
  }
  return counts;
}

function rootChange(plan: SubtreeOutput, key: string): ChangeEntry | undefined {
  return plan.changes.find((change) => change.key === key || change.before.key === key);
}

function text(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function listedIn(parent: string | null, titles: Titles): string | null {
  if (parent === null) {
    return 'the project backlog';
  }
  const holder = named(parent, titles);
  return holder === null ? null : `the backlog of ${holder}`;
}

// Push, before: "Move backlog item 'X' up from batch 'A' to goal 'G'. It
// will be listed in the backlog of goal 'G'."
export function pushPlanText(
  key: string,
  plan: SubtreeOutput,
  titles: Titles,
): string | null {
  const change = rootChange(plan, key);
  const from = text(change?.before.parent);
  const to = text(change?.after.parent);
  const item = named(key, titles);
  const source = from === null ? null : named(from, titles);
  const target = to === null ? 'the project' : named(to, titles);
  const listed = listedIn(to, titles);
  if (
    change === undefined ||
    item === null ||
    source === null ||
    target === null ||
    listed === null
  ) {
    return null;
  }
  return `Move ${item} up from ${source} to ${target}. It will be listed in ${listed}.`;
}

export function pushResultText(
  key: string,
  plan: SubtreeOutput,
  titles: Titles,
): string | null {
  const change = rootChange(plan, key);
  const to = text(change?.after.parent);
  const item = named(key, titles);
  const target = to === null ? 'the project' : named(to, titles);
  const listed = listedIn(to, titles);
  if (change === undefined || item === null || target === null || listed === null) {
    return null;
  }
  return `Moved ${item} up to ${target}. It is now listed in ${listed}.`;
}

export interface MoveFacts {
  key: string;
  parent: string;
  // Known from a server plan; unknown before a move is sent.
  newKey: string | null;
  // What moves along with it, by kind.
  children: Partial<Record<Kind, number>>;
}

// A move, before: "Move subtask 'X' from batch 'A' (goal 'G2') to batch 'B'
// (goal 'G1'). Its key will change to goal-1/batch-2/subtask-16."
export function movePlanText(facts: MoveFacts, titles: Titles): string | null {
  const item = named(facts.key, titles);
  const from = place(parentOf(facts.key), titles);
  const to = place(facts.parent, titles);
  if (item === null || from === null || to === null) {
    return null;
  }
  const along = countsText(facts.children);
  const total = Object.values(facts.children).reduce((sum, count) => sum + count, 0);
  const verb = total === 1 ? 'moves' : 'move';
  const moves = along === '' ? '' : ` Its ${along} ${verb} with it.`;
  const key = facts.newKey === null ? '' : ` Its key will change to ${facts.newKey}.`;
  return `Move ${item} from ${from} to ${to}.${key}${moves}`;
}

// What moves along with an item, from the tree: every entry below it.
export function descendants(
  key: string,
  entries: readonly { item: { key: string } }[],
): Partial<Record<Kind, number>> {
  const counts: Partial<Record<Kind, number>> = {};
  for (const { item } of entries) {
    const kind = kindOf(item.key);
    if (item.key.startsWith(`${key}/`) && kind !== null) {
      counts[kind] = (counts[kind] ?? 0) + 1;
    }
  }
  return counts;
}

export function moveFactsFromPlan(
  key: string,
  parent: string,
  plan: SubtreeOutput,
): MoveFacts {
  return {
    key,
    parent,
    newKey: text(rootChange(plan, key)?.after.key),
    children: others(plan.changes, key),
  };
}

export function moveResultText(facts: MoveFacts, titles: Titles): string | null {
  const item = named(facts.key, titles);
  const to = place(facts.parent, titles);
  if (item === null || to === null) {
    return null;
  }
  const key = facts.newKey === null ? '' : ` Its key is now ${facts.newKey}.`;
  return `Moved ${item} to ${to}.${key}`;
}

// A drop of an item with children: "Drop batch 'B' and its 3 open subtasks."
// The plan lists every item whose state changes, so the rest are open ones.
export function dropPlanText(
  key: string,
  plan: SubtreeOutput,
  titles: Titles,
): string | null {
  const item = named(key, titles);
  if (item === null) {
    return null;
  }
  const along = countsText(others(plan.changes, key));
  return along === ''
    ? `Drop ${item}.`
    : `Drop ${item} and its ${along.replace(/(\d+) /g, '$1 open ')}.`;
}

export function dropResultText(
  key: string,
  plan: SubtreeOutput,
  titles: Titles,
): string | null {
  const planned = dropPlanText(key, plan, titles);
  return planned === null ? null : `Dropped${planned.slice('Drop'.length)}`;
}
