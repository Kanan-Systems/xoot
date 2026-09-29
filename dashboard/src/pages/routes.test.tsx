// The routes: each tab, the ?item drawer over any view, Back and Escape,
// the goal selector, focus and item links with nested keys in the query,
// and the redirects.
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { PROJECT_ID } from '../lib/tree.ts';
import { mockApi, projectRoutes, urlOf } from '../test/api.ts';
import { B1, B1_BACKLOG, G1, P_BACKLOG } from '../test/fixtures.ts';
import { mockReactFlowDom } from '../test/reactFlow.ts';
import { renderApp } from '../test/renderApp.tsx';

function location(): string {
  return screen.getByTestId('location').textContent;
}

async function at(path: string): Promise<void> {
  await waitFor(() => {
    expect(location()).toBe(path);
  });
}

function shownNode(id: string): Element | null {
  return document.querySelector(`.react-flow__node[data-id="${id}"]`);
}

describe('routes', () => {
  let fetchMock: ReturnType<typeof mockApi>;

  beforeEach(() => {
    vi.unstubAllGlobals();
    mockReactFlowDom();
    fetchMock = mockApi(projectRoutes());
  });

  it('/ redirects to the first project tree', async () => {
    renderApp('/');
    await at('/x/tree');
    expect(
      await screen.findByRole('region', { name: 'Item tree' }),
    ).toBeInTheDocument();
  });

  it('/:project redirects to its tree', async () => {
    renderApp('/x');
    await at('/x/tree');
  });

  it('has exactly the Tree, Backlog and Decisions tabs', async () => {
    renderApp('/x/tree');
    const views = await screen.findByRole('navigation', { name: 'Views' });
    const tabs = within(views).getAllByRole('link');
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      'Tree',
      'Backlog',
      'Decisions',
    ]);
  });

  it.each([
    ['Backlog', '/x/backlog'],
    ['Decisions', '/x/decisions'],
    ['Tree', '/x/tree'],
  ])('the %s tab is its own route', async (tab, path) => {
    renderApp('/x/decisions');
    const views = await screen.findByRole('navigation', { name: 'Views' });
    fireEvent.click(within(views).getByRole('link', { name: tab }));
    await at(path);
    expect(within(views).getByRole('link', { name: tab })).toHaveClass('tab-active');
  });

  it('an unknown view says so', async () => {
    renderApp('/x/nowhere');
    expect(await screen.findByText('No such view.')).toBeInTheDocument();
  });

  it('?item with a nested key opens the drawer and fetches it by path', async () => {
    renderApp(`/x/backlog?item=${encodeURIComponent(B1_BACKLOG)}`);
    expect(
      await screen.findByRole('complementary', { name: `Details of ${B1_BACKLOG}` }),
    ).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Backlog' })).toBeInTheDocument();
    const urls = fetchMock.mock.calls.map(([input]) => urlOf(input));
    expect(urls).toContain(`/api/v1/projects/x/items/${B1_BACKLOG}`);
  });

  it('a row click opens the drawer with the key in the query; Back closes it', async () => {
    renderApp('/x/backlog');
    const link = await screen.findByRole('link', {
      name: /title of goal-1\/batch-1\/backlog-1/,
    });
    fireEvent.click(link);
    const expected = `/x/backlog?item=${encodeURIComponent(B1_BACKLOG)}`;
    await at(expected);
    expect(await screen.findByRole('complementary')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Test back' }));
    await at('/x/backlog');
    expect(screen.queryByRole('complementary')).toBeNull();
  });

  it('Escape closes the drawer', async () => {
    renderApp(`/x/decisions?item=${encodeURIComponent(B1)}`);
    await screen.findByRole('complementary', { name: `Details of ${B1}` });
    fireEvent.keyDown(window, { key: 'Escape' });
    await at('/x/decisions');
    expect(screen.queryByRole('complementary')).toBeNull();
  });

  it('a focus deep link round-trips a nested key through the URL', async () => {
    renderApp(`/x/tree?focus=${encodeURIComponent(B1)}`);
    await waitFor(() => {
      expect(shownNode(B1)).not.toBeNull();
    });
    expect(shownNode(G1)).toBeNull();
    expect(shownNode(PROJECT_ID)).toBeNull();
    expect(screen.getByText(/^Focus:/)).toHaveTextContent(`title of ${B1} (${B1})`);
    fireEvent.click(screen.getByRole('link', { name: 'Show the whole tree' }));
    await at('/x/tree');
    await waitFor(() => {
      expect(shownNode(PROJECT_ID)).not.toBeNull();
    });
  });

  it('the drawer focus button moves the key into ?focus', async () => {
    renderApp(`/x/backlog?item=${encodeURIComponent(B1)}`);
    fireEvent.click(await screen.findByRole('button', { name: /Focus on this batch/ }));
    await at(`/x/tree?focus=${encodeURIComponent(B1)}`);
  });

  it.each([
    [`/x/item/${B1}`, `/x/tree?item=${encodeURIComponent(B1)}`],
    [`/x/focus/${B1}`, `/x/tree?focus=${encodeURIComponent(B1)}`],
  ])('the old path link %s redirects into the query', async (from, to) => {
    renderApp(from);
    await at(to);
  });

  it('the goal selector narrows the project-root tree to one goal', async () => {
    renderApp('/x/tree');
    await waitFor(() => {
      expect(shownNode(P_BACKLOG)).not.toBeNull();
    });
    const goal = screen.getByRole('combobox', { name: 'Goal' });
    expect(goal).toHaveValue('');
    expect(within(goal).getAllByRole('option')[0]).toHaveTextContent('All goals');
    fireEvent.change(goal, { target: { value: G1 } });
    await at('/x/tree?goal=goal-1');
    await waitFor(() => {
      expect(shownNode(P_BACKLOG)).toBeNull();
    });
    expect(shownNode(PROJECT_ID)).toBeNull();
    expect(shownNode(G1)).not.toBeNull();
    fireEvent.change(goal, { target: { value: '' } });
    await at('/x/tree');
  });
});
