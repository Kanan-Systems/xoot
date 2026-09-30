// The hierarchy as the server enforces it (services/item_rules.py): a goal
// sits on the project, a batch on a goal, a subtask on a batch. Backlog
// items never move by reparenting; they are covered or pushed. The UI only
// offers what these rules allow; the server checks again.
import type { BacklogRow, ItemKind, ItemSummary, TreeEntry } from '../api/types.gen.ts';
import { truncate } from './display.ts';

type WorkKind = 'goal' | 'batch' | 'subtask';

const CHILD: Partial<Record<ItemKind, WorkKind>> = { goal: 'batch', batch: 'subtask' };
const PARENT: Partial<Record<ItemKind, WorkKind>> = { batch: 'goal', subtask: 'batch' };

// The work kind created under an item of this kind, if any.
export function childKindOf(kind: ItemKind): WorkKind | null {
  return CHILD[kind] ?? null;
}

export function isMovable(kind: ItemKind): boolean {
  return PARENT[kind] !== undefined;
}

export function isDecisionOwner(kind: ItemKind): boolean {
  return kind !== 'backlog';
}

function items(entries: readonly TreeEntry[]): ItemSummary[] {
  return entries.map((entry) => entry.item);
}

// Where an item may be moved: every item of its parent kind but the current
// parent.
export function moveTargets(
  moved: Pick<ItemSummary, 'kind' | 'parent'>,
  entries: readonly TreeEntry[],
): ItemSummary[] {
  const want = PARENT[moved.kind];
  return items(entries).filter(
    (candidate) => candidate.kind === want && candidate.key !== moved.parent,
  );
}

export type DropResult = { ok: true; parent: string } | { ok: false; reason: string };

// What a drop means: the first node under the dragged one that may be its
// new parent, or why there is none.
export function dropTarget(
  dragged: ItemSummary,
  candidates: readonly ItemSummary[],
): DropResult {
  const want = PARENT[dragged.kind];
  if (want === undefined) {
    return { ok: false, reason: 'Only batches and subtasks can be moved.' };
  }
  const fitting = candidates.filter(
    (candidate) => candidate.kind === want && candidate.key !== dragged.key,
  );
  const target = fitting.find((candidate) => candidate.key !== dragged.parent);
  if (target !== undefined) {
    return { ok: true, parent: target.key };
  }
  if (fitting.length > 0) {
    return { ok: false, reason: `${dragged.key} is already there.` };
  }
  return {
    ok: false,
    reason: `Drop a ${dragged.kind} onto a ${want} to move it; it stayed where it was.`,
  };
}

export interface CoverChoice {
  batches: ItemSummary[];
  // The batch a cover lands in when none is named: a batch-level item's own.
  ownBatch: string | null;
}

// The batches a backlog item may be covered in (backlog_service.cover): a
// batch-level item's own batch or another of the same goal, a goal-level
// item's batches of that goal, a project-level item's any batch.
export function coverChoice(
  row: Pick<BacklogRow, 'level' | 'parent'>,
  entries: readonly TreeEntry[],
): CoverChoice {
  const batches = items(entries).filter((candidate) => candidate.kind === 'batch');
  if (row.level === 'project' || row.parent === null) {
    return { batches, ownBatch: null };
  }
  if (row.level === 'goal') {
    return {
      batches: batches.filter((batch) => batch.parent === row.parent),
      ownBatch: null,
    };
  }
  const goal = batches.find((batch) => batch.key === row.parent)?.parent ?? null;
  return {
    batches: batches.filter((batch) => batch.parent === goal),
    ownBatch: row.parent,
  };
}

// The items a decision may be recorded on.
export function decisionOwners(entries: readonly TreeEntry[]): ItemSummary[] {
  return items(entries).filter((candidate) => isDecisionOwner(candidate.kind));
}

// "title (key, state)" for a select option, the title cut so a long one
// cannot widen the select past the drawer.
export function optionLabel(candidate: ItemSummary): string {
  return `${truncate(candidate.title).text} (${candidate.key}, ${candidate.state})`;
}
