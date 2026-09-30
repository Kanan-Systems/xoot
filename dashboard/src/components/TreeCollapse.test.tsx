// Collapsing goals and batches in the rendered tree: the toggle, the child
// count, the recomputed layout, and the per-project storage it survives in.
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Category } from '../api/types.gen.ts';
import { storageKey } from '../lib/collapsed.ts';
import { mockApi, projectRoutes, treeView } from '../test/api.ts';
import {
  B1,
  B2,
  entry,
  G1,
  G1_BACKLOG,
  item,
  P_BACKLOG,
  S3,
} from '../test/fixtures.ts';
import { mockReactFlowDom } from '../test/reactFlow.ts';
import { renderApp } from '../test/renderApp.tsx';

function flowNode(key: string): Promise<HTMLElement> {
  return waitFor(() => {
    const node = document.querySelector<HTMLElement>(
      `.react-flow__node[data-id="${key}"]`,
    );
    expect(node?.style.visibility).toBe('visible');
    return node as HTMLElement;
  });
}

function absent(key: string): Promise<void> {
  return waitFor(() => {
    expect(document.querySelector(`.react-flow__node[data-id="${key}"]`)).toBeNull();
  });
}

describe('collapsing goals and batches', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    mockReactFlowDom();
    mockApi(projectRoutes());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('a toggle hides the children, shows their count and re-lays the tree', async () => {
    renderApp('/x/tree');
    await flowNode(S3);
    const before = (await flowNode(P_BACKLOG)).style.transform;
    const toggle = screen.getByRole('button', { name: `Collapse ${G1}` });
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(toggle);
    await absent(B1);
    await absent(B2);
    await absent(S3);
    await absent(G1_BACKLOG);
    const expand = screen.getByRole('button', { name: `Expand ${G1}` });
    expect(expand).toHaveAttribute('aria-expanded', 'false');
    expect(expand).toHaveTextContent('▸ 3');
    expect(await flowNode(G1)).toHaveAccessibleName(/collapsed, 3 open children/);
    expect((await flowNode(P_BACKLOG)).style.transform).not.toBe(before);
    // The toggle does not open the drawer.
    expect(screen.queryByRole('complementary')).toBeNull();
    fireEvent.click(expand);
    await flowNode(S3);
  });

  it('offers no toggle on subtasks or backlog items', async () => {
    renderApp('/x/tree');
    await flowNode(S3);
    expect(screen.queryByRole('button', { name: `Collapse ${S3}` })).toBeNull();
    expect(screen.queryByRole('button', { name: `Collapse ${P_BACKLOG}` })).toBeNull();
    expect(screen.getByRole('button', { name: `Collapse ${B2}` })).toBeInTheDocument();
  });

  it('persists per project and restores on the next render', async () => {
    const first = renderApp('/x/tree');
    await flowNode(S3);
    fireEvent.click(screen.getByRole('button', { name: `Collapse ${B2}` }));
    await absent(S3);
    expect(localStorage.getItem(storageKey('x'))).toBe(JSON.stringify([B2]));
    first.unmount();
    renderApp('/x/tree');
    await flowNode(B2);
    await absent(S3);
    expect(screen.getByRole('button', { name: `Expand ${B2}` })).toBeInTheDocument();
  });

  it('renders expanded when storage holds garbage', async () => {
    localStorage.setItem(storageKey('x'), '{broken');
    renderApp('/x/tree');
    await flowNode(S3);
    expect(screen.getByRole('button', { name: `Collapse ${G1}` })).toBeInTheDocument();
  });

  it('ignores stored keys of kinds that do not fold', async () => {
    localStorage.setItem(storageKey('x'), JSON.stringify([S3, P_BACKLOG]));
    renderApp('/x/tree');
    await flowNode(S3);
    await flowNode(P_BACKLOG);
  });

  it('still toggles when storage is unavailable', async () => {
    vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {
      throw new Error('denied');
    });
    renderApp('/x/tree');
    await flowNode(S3);
    fireEvent.click(screen.getByRole('button', { name: `Collapse ${B2}` }));
    await absent(S3);
  });
});

// goal-1 > batch-1 with four subtasks in the given categories.
function oneBatch(categories: readonly Category[]) {
  const nodes = [
    entry(item(G1, 'goal', null), 0),
    entry(item(B1, 'batch', G1), 1),
    ...categories.map((category, i) =>
      entry(item(`${B1}/subtask-${String(i + 1)}`, 'subtask', B1, category), 2),
    ),
  ];
  return projectRoutes({ '/projects/x/tree': { ...treeView(), nodes, blocked: [] } });
}

describe('the count on a collapsed node', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    mockReactFlowDom();
  });

  it('counts open work only: three of four subtasks done shows 1', async () => {
    mockApi(oneBatch(['done', 'done', 'done', 'open']));
    renderApp('/x/tree');
    await flowNode(B1);
    fireEvent.click(screen.getByRole('button', { name: `Collapse ${B1}` }));
    const expand = await screen.findByRole('button', { name: `Expand ${B1}` });
    expect(expand).toHaveTextContent(/^▸ 1$/);
    expect(await flowNode(B1)).toHaveAccessibleName(/collapsed, 1 open children/);
  });

  it('shows no count when every child is done or dropped', async () => {
    mockApi(oneBatch(['done', 'done', 'dropped', 'done']));
    renderApp('/x/tree');
    await flowNode(B1);
    fireEvent.click(screen.getByRole('button', { name: `Collapse ${B1}` }));
    const expand = await screen.findByRole('button', { name: `Expand ${B1}` });
    expect(expand).toHaveTextContent(/^▸$/);
    expect(expand).not.toHaveAttribute('title');
    const node = await flowNode(B1);
    expect(node).toHaveAccessibleName(/, collapsed\. Press Enter/);
  });
});
