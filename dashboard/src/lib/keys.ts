// What a nested key says about itself: goal-1/batch-2/subtask-3 is a
// subtask of batch-2 of goal-1. Keys are paths of <kind>-<n> segments.
export type OwnerLevel = 'goal' | 'batch' | 'subtask';

const LEVELS: readonly OwnerLevel[] = ['goal', 'batch', 'subtask'];

function lastKind(key: string): string {
  const last = key.split('/').pop() ?? '';
  return last.replace(/-\d+$/, '');
}

// The goal a key sits under (the goal itself for a goal), or null for a
// project-level key such as backlog-4.
export function goalOf(key: string): string | null {
  const [first] = key.split('/');
  return first?.startsWith('goal-') === true ? first : null;
}

// The level of a decision's owner, from the owner's key.
export function ownerLevel(owner: string): OwnerLevel | null {
  const kind = lastKind(owner);
  return LEVELS.find((level) => level === kind) ?? null;
}

// Natural order, so goal-2 sorts before goal-10.
export function compareKeys(a: string, b: string): number {
  return a.localeCompare(b, 'en', { numeric: true });
}

// A key as an API path: each segment encoded, the slashes kept.
export function keyPath(key: string): string {
  return key.split('/').map(encodeURIComponent).join('/');
}
