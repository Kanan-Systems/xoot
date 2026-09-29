// Live refresh: /changes is polled every POLL_MS, in the background too;
// when the latest event id moves, every query of the project (tree,
// sessions, backlogs, decisions, and any open item or decision) is
// invalidated, so only a real change costs more than one tiny request.
import type { QueryClient } from '@tanstack/react-query';

export const POLL_MS = 2000;

export const queryKeys = {
  projects: () => ['projects'] as const,
  changes: (prefix: string) => ['changes', prefix] as const,
  project: (prefix: string) => ['project', prefix] as const,
  brief: (prefix: string) => ['project', prefix, 'brief'] as const,
  tree: (prefix: string) => ['project', prefix, 'tree'] as const,
  sessions: (prefix: string) => ['project', prefix, 'sessions'] as const,
  session: (prefix: string, key: string) =>
    ['project', prefix, 'session', key] as const,
  backlogs: (prefix: string) => ['project', prefix, 'backlogs'] as const,
  decisions: (prefix: string) => ['project', prefix, 'decisions'] as const,
  item: (key: string) => ['item', key] as const,
  decision: (key: string) => ['decision', key] as const,
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
  await Promise.all([
    client.invalidateQueries({ queryKey: queryKeys.project(prefix) }),
    client.invalidateQueries({ queryKey: ['item'] }),
    client.invalidateQueries({ queryKey: ['decision'] }),
  ]);
}
