import { describe, expect, it } from 'vitest';

import type { TreeEntry } from '../api/types.gen.ts';
import { entry, G1, item } from '../test/fixtures.ts';
import { layout } from './layout.ts';
import { buildGraph, type GraphOptions } from './tree.ts';

const OPTIONS: GraphOptions = {
  showDone: false,
  rootKey: null,
  project: { name: 'Xproj', prefix: 'x' },
  decisionCounts: new Map(),
  blocked: new Map(),
};

// One goal with batch-1..batch-count, in the order the API sends them.
function batches(count: number): { entries: TreeEntry[]; keys: string[] } {
  const keys = Array.from({ length: count }, (_, i) => `${G1}/batch-${String(i + 1)}`);
  return {
    entries: [
      entry(item(G1, 'goal', null), 0),
      ...keys.map((key) => entry(item(key, 'batch', G1), 1)),
    ],
    keys,
  };
}

// Sibling keys from top to bottom, as the left-to-right layout places them.
function topToBottom(entries: TreeEntry[], keys: string[]): string[] {
  const graph = buildGraph(entries, OPTIONS);
  const placed = layout(graph.nodes, graph.edges);
  const y = new Map(placed.map((p) => [p.node.id, p.y]));
  return [...keys].sort((a, b) => (y.get(a) ?? 0) - (y.get(b) ?? 0));
}

describe('layout: sibling order', () => {
  it('keeps three batches in API order', () => {
    const { entries, keys } = batches(3);
    expect(topToBottom(entries, keys)).toEqual(keys);
  });

  it('keeps twelve batches in API order, batch-10 after batch-9', () => {
    const { entries, keys } = batches(12);
    expect(topToBottom(entries, keys)).toEqual(keys);
  });
});
