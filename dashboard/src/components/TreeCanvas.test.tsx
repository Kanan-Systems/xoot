// kanan-74: the real <ReactFlow> renders the nodes, and a click on the
// rendered .react-flow__node wrapper (not an inner button) opens the drawer.
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi, projectRoutes } from '../test/api.ts';
import { mockReactFlowDom } from '../test/reactFlow.ts';
import { renderApp } from '../test/renderApp.tsx';

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

describe('tree node clicks', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    mockReactFlowDom();
    mockApi(projectRoutes());
  });

  it('a click on the node wrapper opens the drawer', async () => {
    renderApp('/x/tree');
    const node = await flowNode('x-2');
    // The browser only delivers the click when the wrapper takes pointer events.
    expect(node.style.pointerEvents).toBe('all');
    fireEvent.click(node);
    expect(
      await screen.findByRole('complementary', { name: 'Details of x-2' }),
    ).toBeInTheDocument();
    expect(location()).toBe('/x/tree?item=x-2');
  });

  it.each(['Enter', ' '])(
    'the key %j on a focused node opens the drawer',
    async (key) => {
      renderApp('/x/tree');
      const node = await flowNode('x-3');
      expect(node).toHaveAttribute('tabindex', '0');
      expect(node).toHaveAccessibleName(
        /Subtask: title of x-3 \(x-3\), open\. Press Enter for details/,
      );
      node.focus();
      fireEvent.keyDown(node, { key });
      await waitFor(() => {
        expect(location()).toBe('/x/tree?item=x-3');
      });
    },
  );

  it('double-click on a goal or batch focuses it', async () => {
    renderApp('/x/tree');
    fireEvent.doubleClick(await flowNode('x-2'));
    await waitFor(() => {
      expect(location()).toBe('/x/focus/x-2');
    });
  });

  it('the focus icon focuses without opening the drawer', async () => {
    renderApp('/x/tree');
    await flowNode('x-1');
    fireEvent.click(screen.getByRole('button', { name: 'Focus on x-1' }));
    await waitFor(() => {
      expect(location()).toBe('/x/focus/x-1');
    });
    expect(screen.queryByRole('complementary')).toBeNull();
  });

  it('Unfiled starts collapsed; a click on the group expands it', async () => {
    renderApp('/x/tree');
    const group = await flowNode('unfiled');
    expect(group).toHaveAttribute('aria-expanded', 'false');
    expect(document.querySelector('.react-flow__node[data-id="x-7"]')).toBeNull();
    fireEvent.click(group);
    await waitFor(() => {
      expect(document.querySelector('.react-flow__node[data-id="x-7"]')).not.toBeNull();
    });
  });
});
