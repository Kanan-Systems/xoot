// A drag-initiated move: nothing is sent before the plain-language
// confirmation; Confirm sends the single request of a childless move, or
// applies a plan that matches what was confirmed; Cancel sends nothing.
// The drop itself is driven through the hook, since jsdom cannot drag.
import { QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { createQueryClient } from '../App.tsx';
import type { ChangeEntry } from '../api/types.gen.ts';
import {
  mockApi,
  projectRoutes,
  requests,
  sequence,
  type Routes,
} from '../test/api.ts';
import { B1, B2, G1, G2, item, S3, sampleTree } from '../test/fixtures.ts';
import { previewed, updated } from '../test/writes.ts';
import { TreeMovePanel, useTreeMove } from './TreeMove.tsx';

const ENTRIES = sampleTree();
const TITLES = new Map(ENTRIES.map((entry) => [entry.item.key, entry.item.title]));
const SUBTASK = item(S3, 'subtask', B2);
const BATCH = item(B2, 'batch', G1);

function Harness({ onNotice }: { onNotice: (message: string) => void }) {
  const tree = useTreeMove('x', ENTRIES, TITLES, onNotice);
  return (
    <>
      <button
        type="button"
        onClick={() => {
          tree.arm(SUBTASK);
        }}
      >
        arm subtask
      </button>
      <button
        type="button"
        onClick={() => {
          tree.arm(BATCH);
        }}
      >
        arm batch
      </button>
      <button
        type="button"
        onClick={() => {
          tree.drop(SUBTASK, B1);
        }}
      >
        drop subtask
      </button>
      <button
        type="button"
        onClick={() => {
          tree.drop(BATCH, G2);
        }}
      >
        drop batch
      </button>
      <output data-testid="armed">{tree.state.armed ?? ''}</output>
      <TreeMovePanel tree={tree} entries={ENTRIES} titles={TITLES} />
    </>
  );
}

function setup(routes: Routes) {
  const fetchMock = mockApi(projectRoutes(routes));
  const onNotice = vi.fn();
  render(
    <QueryClientProvider client={createQueryClient()}>
      <Harness onNotice={onNotice} />
    </QueryClientProvider>,
  );
  return { fetchMock, onNotice };
}

const click = (name: string) => {
  fireEvent.click(screen.getByRole('button', { name }));
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('drag-initiated moves', () => {
  it('ask in plain words before sending a childless move, then send one request', async () => {
    const { fetchMock, onNotice } = setup({
      'POST /projects/x/moves': updated(S3, 'reparent'),
    });
    click('arm subtask');
    click('drop subtask');
    const region = screen.getByRole('region', { name: `Confirm: Move ${S3}` });
    expect(region).toHaveTextContent(
      `Move subtask 'title of ${S3}' from batch 'title of ${B2}' (goal 'title of ${G1}') ` +
        `to batch 'title of ${B1}' (goal 'title of ${G1}').`,
    );
    expect(requests(fetchMock, 'POST')).toHaveLength(0);
    fireEvent.click(within(region).getByRole('button', { name: 'Confirm' }));
    await vi.waitFor(() => {
      expect(onNotice).toHaveBeenLastCalledWith(
        `Moved subtask 'title of ${S3}' to batch 'title of ${B1}' (goal 'title of ${G1}').`,
      );
    });
    expect(requests(fetchMock, 'POST').map((r) => r.body)).toEqual([
      { key: S3, parent: B1, expected_version: 1 },
    ]);
    expect(screen.getByTestId('armed')).toHaveTextContent('');
  });

  it('send nothing on Cancel and disarm', () => {
    const { fetchMock } = setup({});
    click('arm subtask');
    click('drop subtask');
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('region', { name: /Confirm/ })).toBeNull();
    expect(screen.getByTestId('armed')).toHaveTextContent('');
    expect(requests(fetchMock, 'POST')).toHaveLength(0);
  });

  it('apply a plan that moves exactly what was confirmed, without asking twice', async () => {
    const changes: ChangeEntry[] = [
      {
        key: B2,
        before: { key: B2, parent: G1 },
        after: { key: 'goal-2/batch-2', parent: G2 },
      },
      { key: S3, before: { key: S3 }, after: { key: 'goal-2/batch-2/subtask-1' } },
    ];
    const applied = {
      ...previewed('reparent', 'tok-1', changes),
      phase: 'applied' as const,
    };
    const { fetchMock, onNotice } = setup({
      'POST /projects/x/moves': sequence(
        previewed('reparent', 'tok-1', changes),
        applied,
      ),
    });
    click('arm batch');
    click('drop batch');
    expect(
      screen.getByRole('region', { name: `Confirm: Move ${B2}` }),
    ).toHaveTextContent('Its 1 subtask moves with it.');
    click('Confirm');
    await vi.waitFor(() => {
      expect(onNotice).toHaveBeenLastCalledWith(
        `Moved batch 'title of ${B2}' to goal 'title of ${G2}'. Its key is now goal-2/batch-2.`,
      );
    });
    expect(requests(fetchMock, 'POST').map((r) => r.body)).toEqual([
      { key: B2, parent: G2, expected_version: 1 },
      { key: B2, parent: G2, expected_version: 1, confirm_token: 'tok-1' },
    ]);
  });

  it('show the plan when it moves more than was confirmed', async () => {
    const changes: ChangeEntry[] = [
      { key: B2, before: { key: B2 }, after: { key: 'goal-2/batch-2' } },
      { key: S3, before: { key: S3 }, after: { key: 'goal-2/batch-2/subtask-1' } },
      { key: 'goal-1/batch-2/subtask-9', before: {}, after: {} },
    ];
    const { fetchMock } = setup({
      'POST /projects/x/moves': previewed('reparent', 'tok-2', changes),
    });
    click('arm batch');
    click('drop batch');
    click('Confirm');
    const region = await screen.findByRole('region', { name: `Confirm: Move ${B2}` });
    expect(within(region).getByText('Details')).toBeInTheDocument();
    expect(requests(fetchMock, 'POST')).toHaveLength(1);
  });

  it('ignore a drop of a node that is not armed', () => {
    setup({});
    click('arm subtask');
    click('drop batch');
    expect(screen.queryByRole('region', { name: /Confirm/ })).toBeNull();
  });
});
