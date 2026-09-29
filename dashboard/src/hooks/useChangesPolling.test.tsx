import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useChangesPolling } from './useChangesPolling.ts';

const state = vi.hoisted(() => ({ latest: undefined as number | undefined }));
const invalidate = vi.hoisted(() => vi.fn(() => Promise.resolve()));

vi.mock('../api/queries.ts', () => ({
  useChanges: () => ({
    data: state.latest === undefined ? undefined : { latest_event_id: state.latest },
    dataUpdatedAt: 1,
    isError: false,
  }),
}));

vi.mock('../lib/polling.ts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/polling.ts')>()),
  invalidateProject: invalidate,
}));

function setup(prefix: string) {
  const client = new QueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const hook = renderHook(({ project }) => useChangesPolling(project), {
    wrapper,
    initialProps: { project: prefix },
  });
  return { client, hook };
}

describe('useChangesPolling', () => {
  beforeEach(() => {
    state.latest = undefined;
    invalidate.mockClear();
  });

  it('invalidates only when the latest event id moves', () => {
    state.latest = 10;
    const { client, hook } = setup('x');
    expect(invalidate).not.toHaveBeenCalled();
    hook.rerender({ project: 'x' });
    expect(invalidate).not.toHaveBeenCalled();
    state.latest = 11;
    hook.rerender({ project: 'x' });
    expect(invalidate).toHaveBeenCalledTimes(1);
    expect(invalidate).toHaveBeenCalledWith(client, 'x');
  });

  it('starts a new baseline on a project switch', () => {
    state.latest = 10;
    const { hook } = setup('x');
    state.latest = 99;
    hook.rerender({ project: 'y' });
    expect(invalidate).not.toHaveBeenCalled();
  });

  it('reports when it last checked', () => {
    state.latest = 1;
    const { hook } = setup('x');
    expect(hook.result.current).toEqual({ checkedAt: 1, failing: false });
  });
});
