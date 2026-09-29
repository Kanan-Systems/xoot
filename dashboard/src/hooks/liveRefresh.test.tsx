// kanan-75, end to end through the real query client and a mocked fetch:
// a moving /changes id refetches the tree and the new item renders without
// a reload; polling goes on while the page is hidden, and returning to it
// checks at once.
import { QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createQueryClient } from '../App.tsx';
import { useTree } from '../api/queries.ts';
import { mockApi, urlOf } from '../test/api.ts';
import { entry, item } from '../test/fixtures.ts';
import { useChangesPolling } from './useChangesPolling.ts';

function TreeTitles() {
  useChangesPolling('x');
  const tree = useTree('x');
  return (
    <ul>
      {(tree.data?.nodes ?? []).map((node) => (
        <li key={node.item.key}>{node.item.title}</li>
      ))}
    </ul>
  );
}

function setVisibility(state: DocumentVisibilityState): void {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    value: state,
  });
  // Browsers fire it at the document and it bubbles to window, where
  // TanStack Query listens.
  document.dispatchEvent(new Event('visibilitychange', { bubbles: true }));
}

async function advance(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe('live refresh', () => {
  let latest = 10;
  let titles = ['first'];
  let fetchMock: ReturnType<typeof mockApi>;

  const changeCalls = () =>
    fetchMock.mock.calls.filter(([input]) => urlOf(input).includes('/changes')).length;

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    latest = 10;
    titles = ['first'];
    fetchMock = mockApi({
      '/projects/x/changes': () => ({ latest_event_id: latest }),
      '/projects/x/tree': () => ({
        project: 'x',
        truncated: false,
        blocked: [],
        nodes: titles.map((title, index) =>
          entry(item(`goal-${String(index + 1)}`, 'goal', null, 'open', title), 0),
        ),
      }),
    });
    render(
      <QueryClientProvider client={createQueryClient()}>
        <TreeTitles />
      </QueryClientProvider>,
    );
  });

  afterEach(() => {
    setVisibility('visible');
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('refetches the tree when latest_event_id goes from 10 to 11', async () => {
    expect(await screen.findByText('first')).toBeInTheDocument();
    latest = 11;
    titles = ['first', 'LV live refresh ñ'];
    await advance(2100);
    expect(await screen.findByText('LV live refresh ñ')).toBeInTheDocument();
  });

  it('keeps polling every 2 s while the page is hidden', async () => {
    await screen.findByText('first');
    setVisibility('hidden');
    const before = changeCalls();
    await advance(4100);
    expect(changeCalls()).toBeGreaterThanOrEqual(before + 2);
  });

  it('checks at once when the page becomes visible again', async () => {
    await screen.findByText('first');
    setVisibility('hidden');
    latest = 11;
    titles = ['first', 'while away'];
    const before = changeCalls();
    setVisibility('visible');
    await advance(0);
    expect(changeCalls()).toBe(before + 1);
    expect(await screen.findByText('while away')).toBeInTheDocument();
  });
});
