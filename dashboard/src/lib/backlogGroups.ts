// The backlog view's groups: each goal (its own backlog, then each of its
// batches' backlog), then the project backlog. Groups sort by key
// naturally; rows keep the API's order within them. A goal or batch filter
// shows only that group, which may be empty.
import type { BacklogRow, BacklogView, ItemSummary } from '../api/types.gen.ts';
import { batchOf, compareKeys, goalOf } from './keys.ts';

// Keys never contain '@', so the project group cannot collide with one.
export const PROJECT_GROUP = '@project';

export interface BatchGroup {
  batch: string;
  items: BacklogRow[];
}

export interface GoalGroup {
  goal: string;
  // The goal's own backlog, not its batches'.
  items: BacklogRow[];
  batches: BatchGroup[];
}

export interface BacklogTree {
  goals: GoalGroup[];
  project: BacklogRow[];
}

export interface BacklogFilter {
  goal: string | null;
  batch: string | null;
}

// Where a row sits: its goal and, for batch backlog, its batch.
function holders(row: BacklogRow): { goal: string | null; batch: string | null } {
  if (row.parent === null) {
    return { goal: null, batch: null };
  }
  return { goal: goalOf(row.parent), batch: batchOf(row.parent) };
}

export function backlogGoals(view: BacklogView): string[] {
  const goals = new Set(view.items.flatMap((row) => holders(row).goal ?? []));
  return [...goals].sort(compareKeys);
}

// The batches holding backlog, only the goal's when one is chosen.
export function backlogBatches(view: BacklogView, goal: string | null): string[] {
  const batches = new Set(
    view.items.flatMap((row) => {
      const where = holders(row);
      return where.batch !== null && (goal === null || where.goal === goal)
        ? [where.batch]
        : [];
    }),
  );
  return [...batches].sort(compareKeys);
}

// The project's goals and batches, from the tree: a filter may name one of
// them although it holds no open backlog.
export interface Holders {
  goals: readonly string[];
  batches: readonly string[];
}

export const NO_HOLDERS: Holders = { goals: [], batches: [] };

export function holdersOf(entries: readonly { item: ItemSummary }[]): Holders {
  const keys = (kind: string) =>
    entries.flatMap(({ item }) => (item.kind === kind ? [item.key] : []));
  return { goals: keys('goal'), batches: keys('batch') };
}

// A goal or batch of the project is kept even with no open backlog, so the
// view can say so; values that name neither are ignored.
export function validFilter(
  view: BacklogView,
  goal: string | null,
  batch: string | null,
  known: Holders = NO_HOLDERS,
): BacklogFilter {
  const knownGoal =
    goal !== null && (backlogGoals(view).includes(goal) || known.goals.includes(goal))
      ? goal
      : null;
  const inGoal = batch !== null && (knownGoal === null || goalOf(batch) === knownGoal);
  const knownBatch =
    batch !== null &&
    (backlogBatches(view, knownGoal).includes(batch) ||
      (inGoal && known.batches.includes(batch)))
      ? batch
      : null;
  return { goal: knownGoal, batch: knownBatch };
}

// The filter's options, with its own selection among them even when that
// goal or batch holds no backlog, so the control shows what is chosen.
export function filterChoices(
  view: BacklogView,
  filter: BacklogFilter,
): { goals: string[]; batches: string[] } {
  const withChosen = (keys: string[], chosen: string | null) =>
    chosen === null || keys.includes(chosen)
      ? keys
      : [...keys, chosen].sort(compareKeys);
  return {
    goals: withChosen(backlogGoals(view), filter.goal),
    batches: withChosen(backlogBatches(view, filter.goal), filter.batch),
  };
}

function shown(row: BacklogRow, filter: BacklogFilter): boolean {
  const where = holders(row);
  if (filter.batch !== null) {
    return where.batch === filter.batch;
  }
  return filter.goal === null || where.goal === filter.goal;
}

export function backlogTree(view: BacklogView, filter: BacklogFilter): BacklogTree {
  const goals = new Map<string, GoalGroup>();
  const project: BacklogRow[] = [];
  for (const row of view.items) {
    if (!shown(row, filter)) {
      continue;
    }
    const where = holders(row);
    if (where.goal === null) {
      project.push(row);
      continue;
    }
    const group = goals.get(where.goal) ?? { goal: where.goal, items: [], batches: [] };
    goals.set(where.goal, group);
    if (where.batch === null) {
      group.items.push(row);
      continue;
    }
    const batch = group.batches.find((entry) => entry.batch === where.batch);
    if (batch === undefined) {
      group.batches.push({ batch: where.batch, items: [row] });
    } else {
      batch.items.push(row);
    }
  }
  const sorted = [...goals.values()].sort((a, b) => compareKeys(a.goal, b.goal));
  for (const group of sorted) {
    group.batches.sort((a, b) => compareKeys(a.batch, b.batch));
  }
  return { goals: sorted, project };
}

export function goalCount(group: GoalGroup): number {
  return group.batches.reduce(
    (sum, batch) => sum + batch.items.length,
    group.items.length,
  );
}
