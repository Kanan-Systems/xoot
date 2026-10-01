// The browser-only failure, reproduced against the real React Flow store:
// the handler's user node has no measured size, so a drop built its
// rectangles from it found no target anywhere (see flowHarness.tsx).
import type { Viewport } from '@xyflow/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { B1, B2, G1, S3 } from '../test/fixtures.ts';
import {
  dropAt,
  flowItem,
  H,
  measureNodes,
  mountFlow,
  VIEWPORTS,
  W,
} from '../test/flowHarness.tsx';

// One goal's batches in a column, the subtask to the right of its batch.
const NODES = [
  flowItem(B1, 'batch', G1, { x: 0, y: 0 }),
  flowItem(B2, 'batch', G1, { x: 0, y: 300 }),
  flowItem(S3, 'subtask', B2, { x: 400, y: 300 }),
];

describe('dropping onto the real React Flow store', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    measureNodes();
  });

  it('hands the handler a user node without measured sizes', async () => {
    const mounted = await mountFlow(NODES, VIEWPORTS[0] as Viewport);
    const internal = mounted.flow().getInternalNode(S3);
    expect(internal?.measured).toEqual({ width: W, height: H });
    expect(internal?.internals.userNode.measured).toBeUndefined();
    expect(internal?.internals.userNode.width).toBeUndefined();
  });

  it.each(VIEWPORTS)(
    'drops a subtask over the middle of another batch at %o',
    async (viewport) => {
      const mounted = await mountFlow(NODES, viewport);
      dropAt(mounted, viewport, S3, { x: 10, y: 5 });
      expect(mounted.onDrop).toHaveBeenCalledWith(
        expect.objectContaining({ key: S3 }),
        B1,
      );
      expect(mounted.drag().message).toBe('');
    },
  );

  it.each(VIEWPORTS)('still snaps back from empty canvas at %o', async (viewport) => {
    const mounted = await mountFlow(NODES, viewport);
    dropAt(mounted, viewport, S3, { x: 1500, y: 1500 });
    expect(mounted.onDrop).not.toHaveBeenCalled();
  });
});
