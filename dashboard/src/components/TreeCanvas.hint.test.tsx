// The drop hint on the rendered canvas: an arming the page refuses says
// why, and the hint clears on the next pointer-down on the canvas, on
// Escape and when another node is armed.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ItemSummary } from '../api/types.gen.ts';
import { B1, S3, sampleTree } from '../test/fixtures.ts';
import { mockReactFlowDom } from '../test/reactFlow.ts';
import { TreeCanvas } from './TreeCanvas.tsx';
import { WAITING } from './TreeMove.tsx';

function renderCanvas(onArm: (item: ItemSummary) => string | null) {
  render(
    <TreeCanvas
      entries={sampleTree()}
      rootKey={null}
      project={{ name: 'X', prefix: 'x' }}
      decisionCounts={new Map()}
      blocked={new Map()}
      showDone={false}
      collapsed={new Set()}
      onOpen={vi.fn()}
      onFocus={vi.fn()}
      onShowDone={vi.fn()}
      onToggle={vi.fn()}
      onArm={onArm}
    />,
  );
}

function wrapper(id: string): Promise<HTMLElement> {
  return waitFor(() => {
    const node = document.querySelector<HTMLElement>(
      `.react-flow__node[data-id="${id}"]`,
    );
    expect(node?.style.visibility).toBe('visible');
    return node as HTMLElement;
  });
}

const status = () => document.querySelector('.drop-message')?.textContent ?? '';

describe('the drop hint on the canvas', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    mockReactFlowDom();
  });

  it('says why an arming was refused, and clears on the next pointer-down', async () => {
    renderCanvas(() => WAITING);
    fireEvent.doubleClick(await wrapper(B1));
    expect(screen.getByRole('status')).toHaveTextContent(WAITING);
    const pane = document.querySelector('.react-flow__pane');
    if (pane === null) {
      throw new Error('no pane');
    }
    fireEvent.pointerDown(pane);
    expect(status()).toBe('');
  });

  it('clears on Escape', async () => {
    renderCanvas(() => WAITING);
    fireEvent.doubleClick(await wrapper(B1));
    expect(status()).toBe(WAITING);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(status()).toBe('');
  });

  it('clears when another node is armed', async () => {
    const onArm = vi.fn<(item: ItemSummary) => string | null>(() => WAITING);
    renderCanvas(onArm);
    fireEvent.doubleClick(await wrapper(B1));
    expect(status()).toBe(WAITING);
    onArm.mockReturnValue(null);
    fireEvent.doubleClick(await wrapper(S3));
    expect(onArm).toHaveBeenLastCalledWith(expect.objectContaining({ key: S3 }));
    expect(status()).toBe('');
  });
});
