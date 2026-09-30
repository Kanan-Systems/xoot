// Live refresh: /changes is polled every POLL_MS, in the background too;
// when the latest event id moves, every query of the project (tree,
// backlog, decisions, and any open item or decision) is invalidated, so
// only a real change costs more than one tiny request.
import type { QueryClient } from '@tanstack/react-query';

export const POLL_MS = 2000;

export const queryKeys = {
  projects: () => ['projects'] as const,
  changes: (prefix: string) => ['changes', prefix] as const,
  project: (prefix: string) => ['project', prefix] as const,
  tree: (prefix: string) => ['project', prefix, 'tree'] as const,
  backlog: (prefix: string) => ['project', prefix, 'backlog'] as const,
  decisions: (prefix: string) => ['project', prefix, 'decisions'] as const,
  item: (prefix: string, key: string) => ['project', prefix, 'item', key] as const,
  decision: (prefix: string, key: string) =>
    ['project', prefix, 'decision', key] as const,
  workflow: (prefix: string) => ['project', prefix, 'workflow'] as const,
};

// The first reading is a baseline, not a change.
export function changed(
  previous: number | undefined,
  next: number | undefined,
): boolean {
  return previous !== undefined && next !== undefined && previous !== next;
}

export async function invalidateProject(
  client: QueryClient,
  prefix: string,
): Promise<void> {
  await client.invalidateQueries({ queryKey: queryKeys.project(prefix) });
}
