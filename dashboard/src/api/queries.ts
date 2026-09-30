// One hook per endpoint. Project data lives under ['project', prefix] so a
// change detected by polling invalidates all of it at once.
import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { keyPath } from '../lib/keys.ts';
import { queryKeys, POLL_MS } from '../lib/polling.ts';
import { getJson, segment } from './client.ts';
import type {
  BacklogView,
  ChangesView,
  DecisionsView,
  DecisionView,
  ItemView,
  ProjectsOutput,
  TreeView,
  WorkflowView,
} from './types.gen.ts';

// The whole tree: the dashboard collapses done items itself.
export const TREE_QUERY = '?depth=8&include_done=true&limit=1000';

function projectPath(prefix: string): string {
  return `/projects/${segment(prefix)}`;
}

export function useProjects(): UseQueryResult<ProjectsOutput> {
  return useQuery({
    queryKey: queryKeys.projects(),
    queryFn: ({ signal }) => getJson<ProjectsOutput>('/projects', signal),
  });
}

export function useTree(prefix: string): UseQueryResult<TreeView> {
  return useQuery({
    queryKey: queryKeys.tree(prefix),
    queryFn: ({ signal }) =>
      getJson<TreeView>(`${projectPath(prefix)}/tree${TREE_QUERY}`, signal),
  });
}

export function useBacklog(prefix: string): UseQueryResult<BacklogView> {
  return useQuery({
    queryKey: queryKeys.backlog(prefix),
    queryFn: ({ signal }) =>
      getJson<BacklogView>(`${projectPath(prefix)}/backlog`, signal),
  });
}

export function useDecisions(prefix: string): UseQueryResult<DecisionsView> {
  return useQuery({
    queryKey: queryKeys.decisions(prefix),
    queryFn: ({ signal }) =>
      getJson<DecisionsView>(`${projectPath(prefix)}/decisions`, signal),
  });
}

export function useItem(prefix: string, key: string | null): UseQueryResult<ItemView> {
  return useQuery({
    queryKey: queryKeys.item(prefix, key ?? ''),
    queryFn: ({ signal }) =>
      getJson<ItemView>(`${projectPath(prefix)}/items/${keyPath(key ?? '')}`, signal),
    enabled: key !== null,
  });
}

export function useDecision(
  prefix: string,
  key: string,
  enabled: boolean,
): UseQueryResult<DecisionView> {
  return useQuery({
    queryKey: queryKeys.decision(prefix, key),
    queryFn: ({ signal }) =>
      getJson<DecisionView>(`${projectPath(prefix)}/decisions/${keyPath(key)}`, signal),
    enabled,
  });
}

// Every state of each kind and, for a kind that restricts them, its moves.
export function useWorkflow(prefix: string): UseQueryResult<WorkflowView> {
  return useQuery({
    queryKey: queryKeys.workflow(prefix),
    queryFn: ({ signal }) =>
      getJson<WorkflowView>(`${projectPath(prefix)}/workflow`, signal),
  });
}

export function useChanges(prefix: string): UseQueryResult<ChangesView> {
  return useQuery({
    queryKey: queryKeys.changes(prefix),
    queryFn: ({ signal }) =>
      getJson<ChangesView>(`${projectPath(prefix)}/changes`, signal),
    refetchInterval: POLL_MS,
    // A hidden tab keeps polling (browsers may throttle it); returning to
    // the window checks at once instead of waiting for the next tick.
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: 'always',
  });
}
