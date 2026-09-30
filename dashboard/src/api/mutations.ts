// One mutation hook per write route. An applied write invalidates the
// project's queries at once instead of waiting for the next /changes poll;
// a preview changed nothing, so it invalidates nothing.
import {
  useMutation,
  useQueryClient,
  type QueryKey,
  type UseMutationResult,
} from '@tanstack/react-query';

import { keyPath } from '../lib/keys.ts';
import { invalidateProject, queryKeys } from '../lib/polling.ts';
import { segment, sendJson } from './client.ts';
import type {
  CaptureRequest,
  CoverOutput,
  CoverRequest,
  DecisionCreateRequest,
  DecisionOutput,
  DecisionUpdateRequest,
  ItemCreateRequest,
  ItemUpdateOutput,
  ItemUpdateRequest,
  ItemWriteOutput,
  MoveRequest,
  ProjectInfo,
  ProjectRenameRequest,
  PushOutput,
  PushRequest,
} from './types.gen.ts';

// A PATCH names its record in the path and sends the rest as the body.
export interface Patch<B> {
  key: string;
  body: B;
}

function isPreview(result: unknown): boolean {
  return (
    typeof result === 'object' &&
    result !== null &&
    (result as { phase?: unknown }).phase === 'preview'
  );
}

function useWrite<V, R>(
  prefix: string,
  send: (variables: V) => Promise<R>,
  also: readonly QueryKey[] = [],
): UseMutationResult<R, Error, V> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: send,
    // Retrying a write could apply it twice; the user decides.
    retry: false,
    onSuccess: async (result) => {
      if (isPreview(result)) {
        return;
      }
      await Promise.all([
        invalidateProject(client, prefix),
        ...also.map((queryKey) => client.invalidateQueries({ queryKey })),
      ]);
    },
  });
}

function base(prefix: string): string {
  return `/projects/${segment(prefix)}`;
}

export function useCreateItem(prefix: string) {
  return useWrite(prefix, (body: ItemCreateRequest) =>
    sendJson<ItemWriteOutput>('POST', `${base(prefix)}/items`, body),
  );
}

export function useUpdateItem(prefix: string) {
  return useWrite(prefix, ({ key, body }: Patch<ItemUpdateRequest>) =>
    sendJson<ItemUpdateOutput>('PATCH', `${base(prefix)}/items/${keyPath(key)}`, body),
  );
}

export function useMoveItem(prefix: string) {
  return useWrite(prefix, (body: MoveRequest) =>
    sendJson<ItemUpdateOutput>('POST', `${base(prefix)}/moves`, body),
  );
}

export function useCapture(prefix: string) {
  return useWrite(prefix, (body: CaptureRequest) =>
    sendJson<ItemWriteOutput>('POST', `${base(prefix)}/backlog`, body),
  );
}

export function useCover(prefix: string) {
  return useWrite(prefix, (body: CoverRequest) =>
    sendJson<CoverOutput>('POST', `${base(prefix)}/backlog/covers`, body),
  );
}

export function usePush(prefix: string) {
  return useWrite(prefix, (body: PushRequest) =>
    sendJson<PushOutput>('POST', `${base(prefix)}/backlog/pushes`, body),
  );
}

export function useCreateDecision(prefix: string) {
  return useWrite(prefix, (body: DecisionCreateRequest) =>
    sendJson<DecisionOutput>('POST', `${base(prefix)}/decisions`, body),
  );
}

export function useUpdateDecision(prefix: string) {
  return useWrite(prefix, ({ key, body }: Patch<DecisionUpdateRequest>) =>
    sendJson<DecisionOutput>(
      'PATCH',
      `${base(prefix)}/decisions/${keyPath(key)}`,
      body,
    ),
  );
}

// The project list sits outside ['project', prefix], and polling never
// refreshes it, so a rename refreshes it explicitly.
export function useRenameProject(prefix: string) {
  return useWrite(
    prefix,
    (body: ProjectRenameRequest) => sendJson<ProjectInfo>('PATCH', base(prefix), body),
    [queryKeys.projects()],
  );
}
