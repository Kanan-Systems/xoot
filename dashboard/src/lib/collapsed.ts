// Which goals and batches a viewer collapsed, kept per project in this
// browser only. Storage may be missing, full, blocked or hold anything, so
// every access is guarded and a bad value reads as nothing collapsed.

export function storageKey(project: string): string {
  return `xoot:collapsed:${project}`;
}

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function loadCollapsed(project: string): Set<string> {
  try {
    const raw = storage()?.getItem(storageKey(project)) ?? null;
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

export function saveCollapsed(project: string, keys: ReadonlySet<string>): void {
  try {
    const store = storage();
    if (keys.size === 0) {
      store?.removeItem(storageKey(project));
    } else {
      store?.setItem(storageKey(project), JSON.stringify([...keys].sort()));
    }
  } catch {
    // Not saved: the toggle still holds for this page view.
  }
}
