// kanan-74: the real <ReactFlow> renders the nodes, and a click on the
// rendered .react-flow__node wrapper (not an inner button) opens the drawer.
// Also: the project-root tree, backlog nodes and themed zoom controls.
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { PROJECT_ID } from '../lib/tree.ts';
import { mockApi, projectRoutes } from '../test/api.ts';
import { B1, B1_BACKLOG, G1, P_BACKLOG, S3 } from '../test/fixtures.ts';
import { mockReactFlowDom } from '../test/reactFlow.ts';
import { renderApp } from '../test/renderApp.tsx';
import { CONTROLS_CLASS } from './TreeCanvas.tsx';

function flowNode(key: string): Promise<HTMLElement> {
  // Measured nodes are visible; until then React Flow hides them.
  return waitFor(() => {
    const node = document.querySelector<HTMLElement>(
      `.react-flow__node[data-id="${key}"]`,
    );
    expect(node?.style.visibility).toBe('visible');
    return node as HTMLElement;
  });
}

function location(): string {
  return screen.getByTestId('location').textContent;
}

function itemParam(key: string): string {
  return new URLSearchParams({ item: key }).toString();
}

describe('tree node clicks', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    mockReactFlowDom();
    mockApi(projectRoutes());
  });

  it('a click on the node wrapper opens the drawer', async () => {
    renderApp('/x/tree');
    const node = await flowNode(B1);
    // The browser only delivers the click when the wrapper takes pointer events.
    expect(node.style.pointerEvents).toBe('all');
    fireEvent.click(node);
    expect(
      await screen.findByRole('complementary', { name: `Details of ${B1}` }),
    ).toBeInTheDocument();
    expect(location()).toBe(`/x/tree?${itemParam(B1)}`);
  });

  it.each(['Enter', ' '])(
    'the key %j on a focused node opens the drawer',
    async (key) => {
      renderApp('/x/tree');
      const node = await flowNode(S3);
      expect(node).toHaveAttribute('tabindex', '0');
      expect(node).toHaveAccessibleName(
        `Subtask: title of ${S3} (${S3}), open. Press Enter for details`,
      );
      node.focus();
      fireEvent.keyDown(node, { key });
      await waitFor(() => {
        expect(location()).toBe(`/x/tree?${itemParam(S3)}`);
      });
    },
  );

  // A double-click on a batch or subtask arms it for dragging instead
  // (TreeDrag.test.tsx); a batch still focuses from its focus icon.
  it('double-click on a goal focuses it through the query', async () => {
    renderApp('/x/tree');
    fireEvent.doubleClick(await flowNode(G1));
    await waitFor(() => {
      expect(location()).toBe('/x/tree?focus=goal-1');
    });
  });

  it('the focus icon focuses without opening the drawer', async () => {
    renderApp('/x/tree');
    await flowNode(G1);
    fireEvent.click(screen.getByRole('button', { name: `Focus on ${G1}` }));
    await waitFor(() => {
      expect(location()).toBe('/x/tree?focus=goal-1');
    });
    expect(screen.queryByRole('complementary')).toBeNull();
  });
});

describe('the project-root tree', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    mockReactFlowDom();
    mockApi(projectRoutes());
  });

  it('roots at the project, with project backlog under it', async () => {
    renderApp('/x/tree');
    const root = await flowNode(PROJECT_ID);
    expect(root).toHaveTextContent('Xproj');
    expect(root).not.toHaveAttribute('tabindex');
    await flowNode(P_BACKLOG);
    const edge = document.querySelector(
      `.react-flow__edge[data-id="${PROJECT_ID}->${P_BACKLOG}"]`,
    );
    expect(edge).not.toBeNull();
  });

  it('draws backlog nodes distinctly and a blocked batch with its hint', async () => {
    renderApp('/x/tree');
    const backlog = await flowNode(B1_BACKLOG);
    expect(backlog.querySelector('.node')).toHaveClass('node-backlog');
    const batch = await flowNode(B1);
    expect(batch).toHaveTextContent('all subtasks done · 1 backlog open');
    expect(batch).toHaveTextContent(`Cover or push ${B1_BACKLOG} in the Backlog tab`);
    expect(batch).toHaveAccessibleName(/all subtasks done · 1 backlog open/);
  });

  it('gives the zoom controls the theme class', async () => {
    renderApp('/x/tree');
    await flowNode(G1);
    const controls = document.querySelector('.react-flow__controls');
    expect(controls).toHaveClass(CONTROLS_CLASS);
    expect(
      controls?.querySelectorAll('.react-flow__controls-button').length,
    ).toBeGreaterThan(0);
  });
});
