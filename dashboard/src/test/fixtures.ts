// Small builders for tree entries and items used across tests.
import type { Category, ItemKind, ItemSummary, TreeEntry } from '../api/types.gen.ts';

export function item(
  key: string,
  kind: ItemKind,
  parent: string | null,
  category: Category = 'open',
  title = `title of ${key}`,
): ItemSummary {
  return { key, kind, title, state: category, category, parent, version: 1 };
}

export function entry(summary: ItemSummary, depth: number): TreeEntry {
  return { depth, item: summary };
}

export const G1 = 'goal-1';
export const B1 = 'goal-1/batch-1';
export const B1_BACKLOG = 'goal-1/batch-1/backlog-1';
export const B2 = 'goal-1/batch-2';
export const S3 = 'goal-1/batch-2/subtask-1';
export const G1_BACKLOG = 'goal-1/backlog-1';
export const G2 = 'goal-2';
export const P_BACKLOG = 'backlog-1';

// goal-1 > batch-1 (subtasks done and dropped, one open backlog item: it is
// blocked) and batch-2 (one open subtask), plus goal backlog; done goal-2
// with a done batch; project backlog open backlog-1 and done backlog-2.
// Pre-order, as the API sends.
export function sampleTree(): TreeEntry[] {
  return [
    entry(item(G1, 'goal', null), 0),
    entry(item(B1, 'batch', G1), 1),
    entry(item('goal-1/batch-1/subtask-1', 'subtask', B1, 'done'), 2),
    entry(item('goal-1/batch-1/subtask-2', 'subtask', B1, 'dropped'), 2),
    entry(item(B1_BACKLOG, 'backlog', B1), 2),
    entry(item(B2, 'batch', G1), 1),
    entry(item(S3, 'subtask', B2), 2),
    entry(item(G1_BACKLOG, 'backlog', G1), 1),
    entry(item(G2, 'goal', null, 'done'), 0),
    entry(item('goal-2/batch-1', 'batch', G2, 'done'), 1),
    entry(item(P_BACKLOG, 'backlog', null), 0),
    entry(item('backlog-2', 'backlog', null, 'done'), 0),
  ];
}
