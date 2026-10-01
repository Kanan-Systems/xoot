// Drops and armings that cannot go ahead say why instead of vanishing: a
// move waiting for confirmation, one still being sent, or one that failed.
// Arming another node dismisses a failed move; an armed item that a refetch
// removes is disarmed; the panel is brought into view when it asks.
import { QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { createQueryClient } from '../App.tsx';
import type { ChangeEntry, TreeEntry } from '../api/types.gen.ts';
import { mockApi, projectRoutes, type Routes } from '../test/api.ts';
import { B1, B2, G1, G2, item, S3, sampleTree } from '../test/fixtures.ts';
import { previewed } from '../test/writes.ts';
import { FAILED, SENDING, TreeMovePanel, useTreeMove, WAITING } from './TreeMove.tsx';

const ENTRIES = sampleTree();
const TITLES = new Map(ENTRIES.map((entry) => [entry.item.key, entry.item.title]));
const SUBTASK = item(S3, 'subtask', B2);
const BATCH = item(B2, 'batch', G1);

function Harness({ entries }: { entries: readonly TreeEntry[] }) {
  const tree = useTreeMove('x', entries, TITLES, () => undefined);
  const [said, setSaid] = useState('');
  const button = (name: string, act: () => string | null) => (
    <button
      type="button"
      onClick={() => {
        setSaid(act() ?? '');
      }}
    >
      {name}
    </button>
  );
  return (
    <>
      {button('arm subtask', () => tree.arm(SUBTASK))}
      {button('arm batch', () => tree.arm(BATCH))}
      {button('drop subtask', () => tree.drop(SUBTASK, B1))}
      {button('drop batch', () => tree.drop(BATCH, G2))}
      <output data-testid="armed">{tree.state.armed ?? ''}</output>
      <output data-testid="said">{said}</output>
      <TreeMovePanel tree={tree} entries={entries} titles={TITLES} />
    </>
  );
}

function setup(routes: Routes = {}) {
  mockApi(projectRoutes(routes));
  const client = createQueryClient();
  const view = render(
    <QueryClientProvider client={client}>
      <Harness entries={ENTRIES} />
    </QueryClientProvider>,
  );
  const rerender = (entries: readonly TreeEntry[]) => {
    view.rerender(
      <QueryClientProvider client={client}>
        <Harness entries={entries} />
      </QueryClientProvider>,
    );
  };
  return { rerender };
}

// Holds every POST until the test fails it; fails it once it was sent.
function holdPosts(): () => Promise<void> {
  let fail: (() => void) | null = null;
  const fake = globalThis.fetch;
  vi.stubGlobal('fetch', (input: RequestInfo | URL, init?: RequestInit) =>
    init?.method === 'POST'
      ? new Promise((_resolve, reject) => {
          fail = () => {
            reject(new Error('network down'));
          };
        })
      : fake(input, init),
  );
  return async () => {
    await vi.waitFor(() => {
      expect(fail).not.toBeNull();
    });
    await act(async () => {
      fail?.();
      await Promise.resolve();
    });
  };
}

const click = (name: string) => {
  fireEvent.click(screen.getByRole('button', { name }));
};
const said = () => screen.getByTestId('said').textContent;
const armed = () => screen.getByTestId('armed').textContent;

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('refused drops and armings', () => {
  it('a move waiting for confirmation refuses arming and dropping, and says so', () => {
    setup();
    click('arm subtask');
    click('drop subtask');
    click('arm batch');
    expect(said()).toBe(WAITING);
    expect(armed()).toBe(S3);
    click('drop subtask');
    expect(said()).toBe(WAITING);
    expect(screen.getByRole('region', { name: `Confirm: Move ${S3}` })).toBeVisible();
  });

  it('a plan on screen refuses a drop and says so', async () => {
    const changes: ChangeEntry[] = [
      { key: B2, before: { key: B2 }, after: { key: 'goal-2/batch-2' } },
      { key: 'goal-1/batch-2/subtask-9', before: {}, after: {} },
    ];
    setup({ 'POST /projects/x/moves': previewed('reparent', 'tok', changes) });
    click('arm batch');
    click('drop batch');
    click('Confirm');
    await screen.findByRole('button', { name: 'Confirm' });
    click('arm subtask');
    click('drop subtask');
    expect(said()).toBe(WAITING);
  });

  it('a drop while a move is sent or failed says why; arming again dismisses the failure', async () => {
    setup();
    const fail = holdPosts();
    click('arm subtask');
    click('drop subtask');
    click('Confirm');
    click('arm batch');
    click('drop batch');
    expect(said()).toBe(SENDING);
    await fail();
    await screen.findByRole('button', { name: 'Dismiss' });
    click('drop batch');
    expect(said()).toBe(FAILED);
    click('arm subtask');
    expect(said()).toBe('');
    expect(screen.queryByRole('button', { name: 'Dismiss' })).toBeNull();
    expect(armed()).toBe(S3);
  });

  it('disarms when a refetch no longer has the armed item', () => {
    const { rerender } = setup();
    click('arm subtask');
    expect(armed()).toBe(S3);
    rerender(ENTRIES.filter((entry) => entry.item.key !== S3));
    expect(armed()).toBe('');
  });

  it('brings the panel into view when it asks for confirmation', () => {
    const scroll = vi.fn();
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      configurable: true,
      value: scroll,
    });
    try {
      setup();
      click('arm subtask');
      expect(scroll).not.toHaveBeenCalled();
      click('drop subtask');
      expect(scroll).toHaveBeenCalledWith({ block: 'nearest' });
    } finally {
      Reflect.deleteProperty(Element.prototype, 'scrollIntoView');
    }
  });
});
