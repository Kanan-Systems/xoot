// Collapsing goals and batches in the rendered tree: the toggle, the child
// count, the recomputed layout, and the per-project storage it survives in.
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { storageKey } from '../lib/collapsed.ts';
import { mockApi, projectRoutes } from '../test/api.ts';
import { B1, B2, G1, G1_BACKLOG, P_BACKLOG, S3 } from '../test/fixtures.ts';
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
    expect(await flowNode(G1)).toHaveAccessibleName(/collapsed, 3 children/);
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
