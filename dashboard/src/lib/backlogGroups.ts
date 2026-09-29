// The backlog view's tables, by level: each batch's backlog (headed by its
// goal and batch titles), then each goal's, then the project backlog.
// Groups keep the API's order within them; groups sort by key naturally.
import type { BacklogRow, BacklogView } from '../api/types.gen.ts';
import { compareKeys } from './keys.ts';
import type { Titles } from './titles.ts';

export type Level = BacklogRow['level'];

export const LEVEL_ORDER: readonly Level[] = ['batch', 'goal', 'project'];

export const LEVEL_HEADING: Record<Level, string> = {
  batch: 'Batch backlog',
  goal: 'Goal backlog',
  project: 'Project backlog',
};

export interface Holder {
  key: string;
  title: string | null;
}

export interface BacklogGroup {
  id: string;
  level: Level;
  // Outermost first: the goal then the batch; none for the project.
  holders: Holder[];
  items: BacklogRow[];
}

function holdersOf(key: string | null, titles: Titles): Holder[] {
  if (key === null) {
    return [];
  }
  const parts = key.split('/');
  return parts.map((_, index) => {
    const prefix = parts.slice(0, index + 1).join('/');
    return { key: prefix, title: titles.get(prefix) ?? null };
  });
}

export function backlogGroups(view: BacklogView, titles: Titles): BacklogGroup[] {
  const byHolder = new Map<string, BacklogGroup>();
  for (const row of view.items) {
    const id = `${row.level}:${row.parent ?? ''}`;
    const group = byHolder.get(id) ?? {
      id,
      level: row.level,
      holders: holdersOf(row.parent, titles),
      items: [],
    };
    group.items.push(row);
    byHolder.set(id, group);
  }
  const groups = [...byHolder.values()];
  return LEVEL_ORDER.flatMap((level) =>
    groups
      .filter((group) => group.level === level)
      .sort((a, b) => compareKeys(a.id, b.id)),
  );
}
