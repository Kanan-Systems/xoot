// The tree's session filter. "highlight" keeps every item and marks the
// session's; "only" keeps the session's items plus their ancestors, so the
// goal > batch > subtask structure around them stays readable.
import type { TreeEntry } from '../api/types.gen.ts';
import type { FilterMode } from './search.ts';

export interface SessionFilter {
  linked: ReadonlySet<string>;
  mode: FilterMode;
}

export interface Filtered {
  entries: TreeEntry[];
  highlight: ReadonlySet<string> | null;
}

export function applySessionFilter(
  entries: readonly TreeEntry[],
  filter: SessionFilter | null,
): Filtered {
  if (filter === null) {
    return { entries: [...entries], highlight: null };
  }
  if (filter.mode === 'highlight') {
    return { entries: [...entries], highlight: filter.linked };
  }
  const parents = new Map(entries.map((entry) => [entry.item.key, entry.item.parent]));
  const keep = new Set<string>();
  for (const key of filter.linked) {
    let current: string | null | undefined = key;
    // Stops at the top, at a key outside the tree, or at a chain already kept.
    while (typeof current === 'string' && parents.has(current) && !keep.has(current)) {
      keep.add(current);
      current = parents.get(current);
    }
  }
  return {
    entries: entries.filter((entry) => keep.has(entry.item.key)),
    highlight: filter.linked,
  };
}
