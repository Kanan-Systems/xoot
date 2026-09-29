// Titles by key for items and decisions, so a view that only has a key can
// still show the title first. A key the index does not know shows alone.
import type { DecisionsView, TreeView } from '../api/types.gen.ts';

export type Titles = ReadonlyMap<string, string>;

export const NO_TITLES: Titles = new Map();

export function titleIndex(
  tree: TreeView | undefined,
  decisions: DecisionsView | undefined,
): Titles {
  const titles = new Map<string, string>();
  for (const entry of tree?.nodes ?? []) {
    titles.set(entry.item.key, entry.item.title);
  }
  for (const decision of decisions?.decisions ?? []) {
    titles.set(decision.key, decision.title);
  }
  return titles;
}

// "title (key)" as plain text, for select options and headings.
export function labelOf(key: string, titles: Titles): string {
  const title = titles.get(key);
  return title === undefined ? key : `${title} (${key})`;
}
