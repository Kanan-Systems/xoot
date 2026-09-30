// Stored collapsed keys are pruned once a complete tree no longer has them,
// and left alone while the tree is cut, loading or failed.
import { screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { storageKey } from '../lib/collapsed.ts';
import { mockApi, projectRoutes, treeView, urlOf, type Routes } from '../test/api.ts';
import { B2 } from '../test/fixtures.ts';
import { mockReactFlowDom } from '../test/reactFlow.ts';
import { renderApp } from '../test/renderApp.tsx';

const KEY = storageKey('x');
const STORED = JSON.stringify([B2, 'goal-9']);

function stored(): string | null {
  return localStorage.getItem(KEY);
}

async function treeShown(): Promise<void> {
  await waitFor(() => {
    const node = document.querySelector<HTMLElement>(
      '.react-flow__node[data-id="goal-1"]',
    );
    expect(node?.style.visibility).toBe('visible');
  });
}

function open(routes: Routes = {}) {
  const fetchMock = mockApi(projectRoutes(routes));
  renderApp('/x/tree');
  return fetchMock;
}

describe('pruning collapsed keys', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    localStorage.setItem(KEY, STORED);
    mockReactFlowDom();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('forgets keys a complete tree no longer has', async () => {
    open();
    await treeShown();
    await waitFor(() => {
      expect(stored()).toBe(JSON.stringify([B2]));
    });
  });

  it('keeps every key while the tree is truncated', async () => {
    open({ '/projects/x/tree': { ...treeView(), truncated: true } });
    await treeShown();
    expect(stored()).toBe(STORED);
  });

  it('keeps every key when the tree fails to load', async () => {
    const routes = projectRoutes();
    delete routes['/projects/x/tree'];
    mockApi(routes);
    renderApp('/x/tree');
    expect(
      await screen.findByText(/Could not load tree/, {}, { timeout: 3000 }),
    ).toBeInTheDocument();
    expect(stored()).toBe(STORED);
  });

  it('keeps every key while the tree is loading', async () => {
    const fetchMock = mockApi(projectRoutes());
    const hanging = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      urlOf(input).includes('/tree')
        ? new Promise<Response>(() => undefined)
        : fetchMock(input, init),
    );
    vi.stubGlobal('fetch', hanging);
    renderApp('/x/tree');
    expect(await screen.findByText(/Loading tree/)).toBeInTheDocument();
    await waitFor(() => {
      expect(
        hanging.mock.calls.some(([input]) => urlOf(input).includes('/decisions')),
      ).toBe(true);
    });
    expect(stored()).toBe(STORED);
  });

  it('tolerates garbage in storage', async () => {
    localStorage.setItem(KEY, '{not json');
    open();
    await treeShown();
    expect(stored()).toBe('{not json');
  });
});
