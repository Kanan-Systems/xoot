// The routes: each tab, the ?item drawer over any view, Back and Escape,
// the goal selector and the redirects.
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi, projectRoutes } from '../test/api.ts';
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

describe('routes', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    mockReactFlowDom();
    mockApi(projectRoutes());
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

  it.each([
    ['Sessions', '/x/sessions'],
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

  it('?item opens the drawer on top of the current view', async () => {
    renderApp('/x/backlog?item=x-9');
    expect(
      await screen.findByRole('complementary', { name: 'Details of x-9' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Backlog' })).toBeInTheDocument();
  });

  it('a row click opens the drawer; Back closes it', async () => {
    renderApp('/x/backlog');
    const [link] = await screen.findAllByRole('link', { name: 'title of x-9 x-9' });
    fireEvent.click(link as HTMLElement);
    await at('/x/backlog?item=x-9');
    expect(await screen.findByRole('complementary')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Test back' }));
    await at('/x/backlog');
    expect(screen.queryByRole('complementary')).toBeNull();
  });

  it('Escape and the close button close the drawer', async () => {
    renderApp('/x/sessions?item=x-2');
    await screen.findByRole('complementary', { name: 'Details of x-2' });
    fireEvent.keyDown(window, { key: 'Escape' });
    await at('/x/sessions');
    expect(screen.queryByRole('complementary')).toBeNull();
  });

  it('the B4a item link redirects to the drawer on the tree', async () => {
    renderApp('/x/item/x-2');
    await at('/x/tree?item=x-2');
  });

  it('the session filter in "only" mode keeps its items and their ancestors', async () => {
    renderApp('/x/tree?session=x-S1&mode=only');
    // x-S1 links x-2, x-4 (done, collapsed into x-2's badge) and x-7 (unfiled).
    await waitFor(() => {
      expect(document.querySelector('.react-flow__node[data-id="x-2"]')).not.toBeNull();
    });
    const shown = [...document.querySelectorAll<HTMLElement>('.react-flow__node')].map(
      (node) => node.dataset.id,
    );
    expect(shown.sort()).toEqual(['unfiled', 'x-1', 'x-2']);
    expect(screen.getByRole('radio', { name: 'Only this session' })).toBeChecked();
  });

  it('the goal selector sets the tree root', async () => {
    renderApp('/x/tree');
    await waitFor(() => {
      expect(
        document.querySelector('.react-flow__node[data-id="unfiled"]'),
      ).not.toBeNull();
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Goal' }), {
      target: { value: 'x-1' },
    });
    await at('/x/tree?goal=x-1');
    await waitFor(() => {
      expect(document.querySelector('.react-flow__node[data-id="unfiled"]')).toBeNull();
    });
    expect(document.querySelector('.react-flow__node[data-id="x-1"]')).not.toBeNull();
    fireEvent.change(screen.getByRole('combobox', { name: 'Goal' }), {
      target: { value: '' },
    });
    await at('/x/tree');
  });
});
