// One hook per endpoint. Project data lives under ['project', prefix] so a
// change detected by polling invalidates all of it at once.
import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { queryKeys, POLL_MS } from '../lib/polling.ts';
import { getJson, segment } from './client.ts';
import type {
  BacklogsView,
  BriefView,
  ChangesView,
  DecisionsView,
  DecisionView,
  ItemView,
  ProjectsOutput,
  SessionsView,
  SessionView,
  TreeView,
} from './types.gen.ts';

// The whole tree: the dashboard collapses done items itself.
export const TREE_QUERY = '?depth=8&include_done=true&limit=1000';

export function useProjects(): UseQueryResult<ProjectsOutput> {
  return useQuery({
    queryKey: queryKeys.projects(),
    queryFn: ({ signal }) => getJson<ProjectsOutput>('/projects', signal),
  });
}

export function useBrief(prefix: string): UseQueryResult<BriefView> {
  return useQuery({
    queryKey: queryKeys.brief(prefix),
    queryFn: ({ signal }) =>
      getJson<BriefView>(`/projects/${segment(prefix)}/brief`, signal),
  });
}

export function useTree(prefix: string): UseQueryResult<TreeView> {
  return useQuery({
    queryKey: queryKeys.tree(prefix),
    queryFn: ({ signal }) =>
      getJson<TreeView>(`/projects/${segment(prefix)}/tree${TREE_QUERY}`, signal),
  });
}

export function useSessions(prefix: string): UseQueryResult<SessionsView> {
  return useQuery({
    queryKey: queryKeys.sessions(prefix),
    queryFn: ({ signal }) =>
      getJson<SessionsView>(`/projects/${segment(prefix)}/sessions`, signal),
  });
}

export function useSession(
  prefix: string,
  key: string | null,
): UseQueryResult<SessionView> {
  return useQuery({
    queryKey: queryKeys.session(prefix, key ?? ''),
    queryFn: ({ signal }) =>
      getJson<SessionView>(
        `/projects/${segment(prefix)}/sessions/${segment(key ?? '')}`,
        signal,
      ),
    enabled: key !== null,
  });
}

export function useBacklogs(prefix: string): UseQueryResult<BacklogsView> {
  return useQuery({
    queryKey: queryKeys.backlogs(prefix),
    queryFn: ({ signal }) =>
      getJson<BacklogsView>(`/projects/${segment(prefix)}/backlogs`, signal),
  });
}

export function useDecisions(prefix: string): UseQueryResult<DecisionsView> {
  return useQuery({
    queryKey: queryKeys.decisions(prefix),
    queryFn: ({ signal }) =>
      getJson<DecisionsView>(`/projects/${segment(prefix)}/decisions`, signal),
  });
}

export function useItem(key: string | null): UseQueryResult<ItemView> {
  return useQuery({
    queryKey: queryKeys.item(key ?? ''),
    queryFn: ({ signal }) => getJson<ItemView>(`/items/${segment(key ?? '')}`, signal),
    enabled: key !== null,
  });
}

export function useDecision(
  key: string,
  enabled: boolean,
): UseQueryResult<DecisionView> {
  return useQuery({
    queryKey: queryKeys.decision(key),
    queryFn: ({ signal }) =>
      getJson<DecisionView>(`/decisions/${segment(key)}`, signal),
    enabled,
  });
}

export function useChanges(prefix: string): UseQueryResult<ChangesView> {
  return useQuery({
    queryKey: queryKeys.changes(prefix),
    queryFn: ({ signal }) =>
      getJson<ChangesView>(`/projects/${segment(prefix)}/changes`, signal),
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: false,
  });
}
