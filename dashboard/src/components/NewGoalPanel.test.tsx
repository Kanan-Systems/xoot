// "New goal" opens a create panel in the drawer slot: one panel at a time,
// closed by Escape or its Close button, opening the new goal when done.
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { itemView, mockApi, projectRoutes, requests, writeError } from '../test/api.ts';
import { G1 } from '../test/fixtures.ts';
import { mockReactFlowDom } from '../test/reactFlow.ts';
import { renderApp } from '../test/renderApp.tsx';
import { detail } from '../test/writes.ts';

const location = () => screen.getByTestId('location').textContent;

function flowNode(key: string): Promise<HTMLElement> {
  return waitFor(() => {
    const node = document.querySelector<HTMLElement>(
      `.react-flow__node[data-id="${key}"]`,
    );
    expect(node?.style.visibility).toBe('visible');
    return node as HTMLElement;
  });
}

async function openPanel() {
  fireEvent.click(await screen.findByRole('button', { name: 'New goal' }));
  return screen.findByRole('complementary', { name: 'New goal' });
}

describe('the new-goal panel', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    mockReactFlowDom();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('opens in the drawer slot, not in the toolbar, with the title focused', async () => {
    mockApi(projectRoutes());
    renderApp('/x/tree');
    const panel = await openPanel();
    expect(location()).toBe('/x/tree?create=goal');
    expect(within(panel).getByLabelText('Title')).toHaveFocus();
    expect(document.querySelector('.tree-toolbar form')).toBeNull();
  });

  it('creates the goal, then opens its drawer in place of the panel', async () => {
    const fetchMock = mockApi(
      projectRoutes({
        'POST /projects/x/items': {
          project: 'x',
          item: detail('goal-3', { kind: 'goal' }),
        },
        '/projects/x/items/goal-3': itemView('goal-3'),
      }),
    );
    renderApp('/x/tree');
    const panel = await openPanel();
    fireEvent.change(within(panel).getByLabelText('Title'), {
      target: { value: 'Ship' },
    });
    fireEvent.click(within(panel).getByRole('button', { name: 'Add goal' }));
    expect(
      await screen.findByRole('complementary', { name: 'Details of goal-3' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('complementary', { name: 'New goal' })).toBeNull();
    expect(requests(fetchMock, 'POST').map((r) => r.body)).toEqual([
      { kind: 'goal', title: 'Ship', body: '' },
    ]);
  });

  it('shows a refused create and keeps the panel', async () => {
    mockApi(
      projectRoutes({
        'POST /projects/x/items': writeError(
          422,
          'ValidationError',
          'invalid arguments',
        ),
      }),
    );
    renderApp('/x/tree');
    const panel = await openPanel();
    fireEvent.change(within(panel).getByLabelText('Title'), {
      target: { value: 'Ship' },
    });
    fireEvent.click(within(panel).getByRole('button', { name: 'Add goal' }));
    expect(await within(panel).findByRole('alert')).toHaveTextContent(
      'invalid arguments',
    );
  });

  it('closes when an item drawer opens, and the other way round', async () => {
    mockApi(projectRoutes());
    renderApp('/x/tree');
    await openPanel();
    fireEvent.click(await flowNode(G1));
    expect(
      await screen.findByRole('complementary', { name: `Details of ${G1}` }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('complementary', { name: 'New goal' })).toBeNull();
    await openPanel();
    expect(
      screen.queryByRole('complementary', { name: `Details of ${G1}` }),
    ).toBeNull();
    expect(location()).toBe('/x/tree?create=goal');
  });

  it('closes with Escape, even from its title field, and with Close', async () => {
    mockApi(projectRoutes());
    renderApp('/x/tree');
    let panel = await openPanel();
    fireEvent.keyDown(within(panel).getByLabelText('Title'), { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByRole('complementary', { name: 'New goal' })).toBeNull();
    });
    panel = await openPanel();
    fireEvent.click(within(panel).getByRole('button', { name: /Close/ }));
    await waitFor(() => {
      expect(location()).toBe('/x/tree');
    });
  });

  it('a second click on an open item stacks no history entry', async () => {
    mockApi(projectRoutes({ [`/projects/x/items/${G1}`]: itemView(G1) }));
    renderApp('/x/tree');
    const node = await flowNode(G1);
    fireEvent.click(node);
    fireEvent.click(node);
    await screen.findByRole('complementary', { name: `Details of ${G1}` });
    fireEvent.click(screen.getByRole('button', { name: 'Test back' }));
    await waitFor(() => {
      expect(location()).toBe('/x/tree');
    });
  });
});
