// The drop rules at zoom 0.6, 1 and 1.4 with pan offsets, against the real
// React Flow store: the pointer is converted with screenToFlowPosition and
// sizes come from xyflow's measurement, so every case must decide the same
// at every viewport (see flowHarness.tsx; nodes are 260x128).
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { NO_TARGET } from '../lib/dropTarget.ts';
import { B1, B2, G1, G2, item, S3 } from '../test/fixtures.ts';
import {
  dropAt,
  flowItem,
  measureNodes,
  mountFlow,
  VIEWPORTS,
  W,
} from '../test/flowHarness.tsx';

const B3 = 'goal-1/batch-3';
const B4 = 'goal-1/batch-4';

// B1 and B3 are 32px apart; B4 is collapsed.
const NODES = [
  flowItem(G1, 'goal', null, { x: -400, y: 0 }),
  flowItem(G2, 'goal', null, { x: -400, y: 300 }),
  flowItem(B1, 'batch', G1, { x: 0, y: 0 }),
  flowItem(B3, 'batch', G1, { x: 0, y: 160 }),
  flowItem(B2, 'batch', G1, { x: 0, y: 600 }),
  flowItem(S3, 'subtask', B2, { x: 400, y: 600 }),
  flowItem(B4, 'batch', G1, { x: 0, y: 900 }, true),
];

const SUBTASK = item(S3, 'subtask', B2);

describe.each(VIEWPORTS)('drop rules at %o', (viewport) => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    measureNodes();
  });

  async function drop(
    at: { x: number; y: number },
    pointer?: { x: number; y: number },
  ) {
    const mounted = await mountFlow(NODES, viewport);
    dropAt(mounted, viewport, S3, at, pointer);
    return mounted;
  }

  it('accepts the batch under the pointer, even with a small overlap', async () => {
    // A 10% overlap; the pointer is inside B1.
    const mounted = await drop({ x: 0, y: -115 }, { x: 130, y: 5 });
    expect(mounted.onDrop).toHaveBeenCalledWith(SUBTASK, B1);
  });

  it('refuses a node that only touches the target edge', async () => {
    const mounted = await drop({ x: W, y: 0 });
    expect(mounted.onDrop).not.toHaveBeenCalled();
    expect(mounted.drag().message).toBe(NO_TARGET);
  });

  it('refuses a 24% overlap with the pointer outside', async () => {
    const mounted = await drop({ x: W - 0.24 * W, y: 0 }, { x: W + 50, y: 64 });
    expect(mounted.onDrop).not.toHaveBeenCalled();
    expect(mounted.drag().message).toBe(NO_TARGET);
  });

  it('accepts a 26% overlap with the pointer outside', async () => {
    const mounted = await drop({ x: W - 0.26 * W, y: 0 }, { x: W + 50, y: 64 });
    expect(mounted.onDrop).toHaveBeenCalledWith(SUBTASK, B1);
  });

  it('of two overlapping candidates, the one under the pointer wins', async () => {
    // 40 rows over B1 (31%), 56 over B3 (44%).
    const at = { x: 0, y: 88 };
    const mounted = await drop(at, { x: 130, y: 100 });
    expect(mounted.onDrop).toHaveBeenCalledWith(SUBTASK, B1);
  });

  it('of two overlapping candidates, the larger overlap wins with the pointer between', async () => {
    const mounted = await drop({ x: 0, y: 88 }, { x: 130, y: 140 });
    expect(mounted.onDrop).toHaveBeenCalledWith(SUBTASK, B3);
  });

  it('refuses its own parent', async () => {
    const mounted = await drop({ x: 0, y: 600 });
    expect(mounted.onDrop).not.toHaveBeenCalled();
    expect(mounted.drag().message).toBe(`${S3} is already there.`);
  });

  it('refuses a node of the wrong kind', async () => {
    const mounted = await drop({ x: -400, y: 0 });
    expect(mounted.onDrop).not.toHaveBeenCalled();
    expect(mounted.drag().message).toBe(NO_TARGET);
  });

  it('refuses a collapsed batch', async () => {
    const mounted = await drop({ x: 0, y: 900 });
    expect(mounted.onDrop).not.toHaveBeenCalled();
    expect(mounted.drag().message).toBe(NO_TARGET);
  });

  it('drops a batch onto a goal', async () => {
    const mounted = await mountFlow(NODES, viewport);
    dropAt(mounted, viewport, B1, { x: -390, y: 310 });
    expect(mounted.onDrop).toHaveBeenCalledWith(
      expect.objectContaining({ key: B1 }),
      G2,
    );
  });

  it('snaps back with the reason the parent gives when it refuses', async () => {
    const mounted = await mountFlow(NODES, viewport);
    mounted.onDrop.mockReturnValue('A move is waiting for your confirmation.');
    dropAt(mounted, viewport, S3, { x: 0, y: 0 });
    expect(mounted.drag().message).toBe('A move is waiting for your confirmation.');
    expect(mounted.drag().dragged).toBeNull();
  });
});
