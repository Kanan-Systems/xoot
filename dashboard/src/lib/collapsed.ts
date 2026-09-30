// What a viewer collapsed, kept per project and per view in this browser
// only: the tree's goals and batches, the decisions view's headings. Storage
// may be missing, full, blocked or hold anything, so every access is guarded
// and a bad value reads as nothing collapsed.

export type CollapseView = 'tree' | 'decisions';

export function storageKey(project: string, view: CollapseView = 'tree'): string {
  return view === 'tree'
    ? `xoot:collapsed:${project}`
    : `xoot:${view}-collapsed:${project}`;
}

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function loadCollapsed(
  project: string,
  view: CollapseView = 'tree',
): Set<string> {
  try {
    const raw = storage()?.getItem(storageKey(project, view)) ?? null;
    if (raw === null) {
      return new Set();
    }
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return new Set();
    }
    return new Set(parsed.filter((key): key is string => typeof key === 'string'));
  } catch {
    return new Set();
  }
}

export function saveCollapsed(
  project: string,
  keys: ReadonlySet<string>,
  view: CollapseView = 'tree',
): void {
  try {
    const store = storage();
    if (keys.size === 0) {
      store?.removeItem(storageKey(project, view));
    } else {
      store?.setItem(storageKey(project, view), JSON.stringify([...keys].sort()));
    }
  } catch {
    // Not saved: the toggle still holds for this page view.
  }
}

// The stored keys that still name an item, or null when all of them do.
// Only a complete tree may prune: a cut one would drop keys it cannot see.
export function pruned(
  keys: ReadonlySet<string>,
  existing: ReadonlySet<string>,
): Set<string> | null {
  const kept = new Set([...keys].filter((key) => existing.has(key)));
  return kept.size === keys.size ? null : kept;
}
