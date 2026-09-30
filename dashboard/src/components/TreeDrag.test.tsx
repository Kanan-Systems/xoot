// Armed dragging in the rendered tree: no node is draggable until a
// double-click arms a batch or subtask; one is armed at a time; Escape and a
// click on empty canvas disarm; goals and backlog are never armed. The drag
// itself needs a real browser.
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { itemView, mockApi, projectRoutes } from '../test/api.ts';
import { B1_BACKLOG, B2, G1, S3 } from '../test/fixtures.ts';
import { mockReactFlowDom } from '../test/reactFlow.ts';
import { renderApp } from '../test/renderApp.tsx';
import { ARMED_HINT } from './TreeCanvas.tsx';

function wrapper(id: string): Promise<HTMLElement> {
  return waitFor(() => {
    const node = document.querySelector<HTMLElement>(
      `.react-flow__node[data-id="${id}"]`,
    );
    expect(node?.style.visibility).toBe('visible');
    return node as HTMLElement;
  });
}

function draggable(): string[] {
  return [...document.querySelectorAll<HTMLElement>('.react-flow__node.draggable')].map(
    (node) => node.dataset.id ?? '',
  );
}

const location = () => screen.getByTestId('location').textContent;

// What a real double-click delivers: two clicks, then the double-click.
async function doubleClick(id: string) {
  const node = await wrapper(id);
  fireEvent.click(node);
  fireEvent.click(node);
  fireEvent.doubleClick(node);
  return node;
}

describe('armed dragging', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    mockReactFlowDom();
    mockApi(projectRoutes({ [`/projects/x/items/${B2}`]: itemView(B2) }));
  });

  it('no node can be dragged until one is armed', async () => {
    renderApp('/x/tree');
    await wrapper(B2);
    expect(draggable()).toEqual([]);
  });

  it('a double-click arms a batch, highlights it, says how, and closes the drawer', async () => {
    renderApp('/x/tree');
    const node = await doubleClick(B2);
    await waitFor(() => {
      expect(draggable()).toEqual([B2]);
    });
    expect(node).toHaveClass('node-armed');
    expect(node.getAttribute('aria-label')).toContain(ARMED_HINT);
    expect(screen.getByText(`${B2} is armed. ${ARMED_HINT}`)).toBeInTheDocument();
    // The clicks opened the drawer; arming closed it, leaving no entry.
    await waitFor(() => {
      expect(location()).toBe('/x/tree');
    });
    expect(screen.queryByRole('complementary')).toBeNull();
  });

  it('a click on the armed node does not reopen the drawer; other nodes still open it', async () => {
    renderApp('/x/tree');
    const node = await doubleClick(B2);
    await waitFor(() => {
      expect(draggable()).toEqual([B2]);
    });
    fireEvent.click(node);
    expect(location()).toBe('/x/tree');
    expect(screen.queryByRole('complementary')).toBeNull();
    fireEvent.click(await wrapper(G1));
    await waitFor(() => {
      expect(location()).toBe(`/x/tree?item=${G1}`);
    });
  });

  it('keeps one armed node: arming another moves it', async () => {
    renderApp('/x/tree');
    await doubleClick(B2);
    await doubleClick(S3);
    await waitFor(() => {
      expect(draggable()).toEqual([S3]);
    });
  });

  it('disarms on Escape and on a click on empty canvas', async () => {
    renderApp('/x/tree');
    await doubleClick(B2);
    await waitFor(() => {
      expect(draggable()).toEqual([B2]);
    });
    fireEvent.keyDown(window, { key: 'Escape' });
    await waitFor(() => {
      expect(draggable()).toEqual([]);
    });
    await doubleClick(S3);
    await waitFor(() => {
      expect(draggable()).toEqual([S3]);
    });
    const pane = document.querySelector('.react-flow__pane');
    if (pane === null) {
      throw new Error('no pane');
    }
    fireEvent.click(pane);
    await waitFor(() => {
      expect(draggable()).toEqual([]);
    });
  });

  it('never arms a goal or a backlog item', async () => {
    renderApp('/x/tree');
    await doubleClick(B1_BACKLOG);
    fireEvent.doubleClick(await wrapper(G1));
    await waitFor(() => {
      expect(location()).toBe('/x/tree?focus=goal-1');
    });
    expect(draggable()).toEqual([]);
  });
});
