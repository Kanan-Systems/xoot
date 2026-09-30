// Which rendered tree nodes React Flow lets the pointer drag: batches and
// subtasks only. The drag itself needs a real browser.
import { waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi, projectRoutes } from '../test/api.ts';
import { B1_BACKLOG, B2, G1, S3 } from '../test/fixtures.ts';
import { mockReactFlowDom } from '../test/reactFlow.ts';
import { renderApp } from '../test/renderApp.tsx';

function wrapper(id: string): Promise<HTMLElement> {
  return waitFor(() => {
    const node = document.querySelector<HTMLElement>(
      `.react-flow__node[data-id="${id}"]`,
    );
    expect(node).not.toBeNull();
    return node as HTMLElement;
  });
}

describe('draggable tree nodes', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    mockReactFlowDom();
    mockApi(projectRoutes());
  });

  it('are the batches and subtasks, never goals, backlog or the project', async () => {
    renderApp('/x/tree');
    expect(await wrapper(B2)).toHaveClass('draggable');
    expect(await wrapper(S3)).toHaveClass('draggable');
    expect(await wrapper(G1)).not.toHaveClass('draggable');
    expect(await wrapper(B1_BACKLOG)).not.toHaveClass('draggable');
    expect(await wrapper('@project')).not.toHaveClass('draggable');
  });
});
