// Small builders for tree entries and items used across tests.
import type { Category, ItemKind, ItemSummary, TreeEntry } from '../api/types.gen.ts';

export function item(
  key: string,
  kind: ItemKind,
  parent: string | null,
  category: Category = 'open',
  title = `title of ${key}`,
): ItemSummary {
  return {
    key,
    kind,
    title,
    state: category,
    category,
    parent,
    backlog_session: null,
    version: 1,
  };
}

export function entry(summary: ItemSummary, depth: number, unfiled = false): TreeEntry {
  return { depth, unfiled, item: summary };
}

// goal x-1 > batch x-2 > subtasks x-3 (open), x-4 (done); done goal x-5 with
// batch x-6; unfiled x-7 (open) and x-8 (dropped). Pre-order, as the API sends.
export function sampleTree(): TreeEntry[] {
  return [
    entry(item('x-1', 'goal', null), 0),
    entry(item('x-2', 'batch', 'x-1'), 1),
    entry(item('x-3', 'subtask', 'x-2'), 2),
    entry(item('x-4', 'subtask', 'x-2', 'done'), 2),
    entry(item('x-5', 'goal', null, 'done'), 0),
    entry(item('x-6', 'batch', 'x-5'), 1),
    entry(item('x-7', 'subtask', null), 0, true),
    entry(item('x-8', 'subtask', null, 'dropped'), 0, true),
  ];
}
