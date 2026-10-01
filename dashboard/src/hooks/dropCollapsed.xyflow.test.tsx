// Collapsed goals and batches as drop targets, against the real React Flow
// store at every viewport. The nodes come from buildGraph, so what is drawn
// is exactly what the tree draws: a collapsed node is drawn (only its
// children are hidden) and accepts a drop; a node under a collapsed parent,
// or a done one folded away, is not drawn and is never a target.
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { TreeEntry } from '../api/types.gen.ts';
import { NO_TARGET } from '../lib/dropTarget.ts';
import { buildGraph } from '../lib/tree.ts';
import { B1, B2, entry, G1, G2, item, S3 } from '../test/fixtures.ts';
import { dropAt, measureNodes, mountFlow, VIEWPORTS } from '../test/flowHarness.tsx';
import type { FlowNode } from './useTreeDrag.ts';

const B1_SUBTASK = 'goal-1/batch-1/subtask-1';
const DONE_BATCH = 'goal-1/batch-3';
const G2_BATCH = 'goal-2/batch-1';

const ENTRIES: TreeEntry[] = [
  entry(item(G1, 'goal', null), 0),
  entry(item(B1, 'batch', G1), 1),
  entry(item(B1_SUBTASK, 'subtask', B1), 2),
  entry(item(B2, 'batch', G1), 1),
  entry(item(S3, 'subtask', B2), 2),
  entry(item(DONE_BATCH, 'batch', G1, 'done'), 1),
  entry(item(G2, 'goal', null), 0),
  entry(item(G2_BATCH, 'batch', G2), 1),
];

// Where each node would sit; the hidden ones get a spot of their own so a
// drop there finds nothing but them.
const AT: Record<string, { x: number; y: number }> = {
  [G1]: { x: -400, y: 0 },
  [G2]: { x: -400, y: 300 },
  [B1]: { x: 0, y: 0 },
  [B1_SUBTASK]: { x: 400, y: 0 },
  [B2]: { x: 0, y: 600 },
  [S3]: { x: 400, y: 600 },
  [G2_BATCH]: { x: 0, y: 900 },
  [DONE_BATCH]: { x: 0, y: 1200 },
};

function drawn(): FlowNode[] {
  const graph = buildGraph(ENTRIES, {
    showDone: false,
    rootKey: null,
    project: { name: 'x', prefix: 'x' },
    decisionCounts: new Map(),
    blocked: new Map(),
    collapsed: new Set([B1, G2]),
  });
  return graph.nodes.flatMap((node) =>
    node.type === 'item' ? [{ ...node, position: AT[node.id] ?? { x: 0, y: 0 } }] : [],
  );
}

describe.each(VIEWPORTS)('collapsed drop targets at %o', (viewport) => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    measureNodes();
  });

  it('draws the collapsed nodes and leaves the hidden ones out', () => {
    const ids = drawn().map((node) => node.id);
    expect(ids).toEqual(expect.arrayContaining([B1, G2, S3, B2]));
    expect(ids).not.toContain(B1_SUBTASK);
    expect(ids).not.toContain(G2_BATCH);
    expect(ids).not.toContain(DONE_BATCH);
  });

  it('a collapsed batch accepts a subtask', async () => {
    const mounted = await mountFlow(drawn(), viewport);
    dropAt(mounted, viewport, S3, { x: 10, y: 5 });
    expect(mounted.onDrop).toHaveBeenCalledWith(
      expect.objectContaining({ key: S3 }),
      B1,
    );
    expect(mounted.drag().message).toBe('');
  });

  it('a collapsed goal accepts a batch', async () => {
    const mounted = await mountFlow(drawn(), viewport);
    dropAt(mounted, viewport, B2, { x: -390, y: 310 });
    expect(mounted.onDrop).toHaveBeenCalledWith(
      expect.objectContaining({ key: B2 }),
      G2,
    );
  });

  it('a batch hidden under a collapsed goal is not a target', async () => {
    const mounted = await mountFlow(drawn(), viewport);
    dropAt(mounted, viewport, S3, AT[G2_BATCH] ?? { x: 0, y: 0 });
    expect(mounted.onDrop).not.toHaveBeenCalled();
    expect(mounted.drag().message).toBe(NO_TARGET);
  });

  it('a done batch folded away is not a target', async () => {
    const mounted = await mountFlow(drawn(), viewport);
    dropAt(mounted, viewport, S3, AT[DONE_BATCH] ?? { x: 0, y: 0 });
    expect(mounted.onDrop).not.toHaveBeenCalled();
    expect(mounted.drag().message).toBe(NO_TARGET);
  });
});
