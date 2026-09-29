import { describe, expect, it } from 'vitest';

import { sampleTree } from '../test/fixtures.ts';
import {
  buildGraph,
  collapseDone,
  countByScope,
  focusSubtree,
  overlay,
  ROOT_ID,
  UNFILED_ID,
  type GraphOptions,
} from './tree.ts';

const OPTIONS: GraphOptions = {
  showDone: false,
  focusKey: null,
  decisionCounts: new Map(),
  highlight: null,
  unfiledOpen: true,
};

function keys(entries: readonly { item: { key: string } }[]): string[] {
  return entries.map((entry) => entry.item.key);
}

describe('collapseDone', () => {
  it('hides done and dropped branches and counts them per parent', () => {
    const { visible, hiddenDone } = collapseDone(sampleTree(), false);
    expect(keys(visible)).toEqual(['x-1', 'x-2', 'x-3', 'x-7']);
    expect(hiddenDone.get('x-2')).toBe(1);
    expect(hiddenDone.get(ROOT_ID)).toBe(1);
    expect(hiddenDone.get(UNFILED_ID)).toBe(1);
    // x-6 is hidden with its done parent and is not counted again.
    expect(hiddenDone.get('x-5')).toBeUndefined();
  });

  it('shows everything when asked', () => {
    const { visible, hiddenDone } = collapseDone(sampleTree(), true);
    expect(visible).toHaveLength(8);
    expect(hiddenDone.size).toBe(0);
  });

  it('keeps the named entry even when it is done', () => {
    const { visible } = collapseDone(focusSubtree(sampleTree(), 'x-5'), false, 'x-5');
    expect(keys(visible)).toEqual(['x-5', 'x-6']);
  });
});

describe('focusSubtree', () => {
  it('returns the root and its descendants only', () => {
    expect(keys(focusSubtree(sampleTree(), 'x-2'))).toEqual(['x-2', 'x-3', 'x-4']);
  });

  it('is empty for an unknown key', () => {
    expect(focusSubtree(sampleTree(), 'x-99')).toEqual([]);
  });
});

describe('buildGraph', () => {
  it('adds an Unfiled group node with edges to the unfiled subtasks', () => {
    const graph = buildGraph(sampleTree(), OPTIONS);
    const group = graph.nodes.find((node) => node.id === UNFILED_ID);
    expect(group?.type).toBe('unfiled');
    expect(group?.data).toMatchObject({ count: 1, hiddenDone: 1 });
    expect(graph.edges.map((edge) => edge.id)).toEqual([
      'x-1->x-2',
      'x-2->x-3',
      'unfiled->x-7',
    ]);
    expect(graph.hiddenTopLevel).toBe(1);
  });

  it('keeps the Unfiled group collapsed when closed: a count, no subtask nodes', () => {
    const graph = buildGraph(sampleTree(), { ...OPTIONS, unfiledOpen: false });
    const group = graph.nodes.find((node) => node.id === UNFILED_ID);
    expect(group?.data).toMatchObject({ count: 1, hiddenDone: 1, open: false });
    expect(graph.nodes.map((node) => node.id)).not.toContain('x-7');
    expect(graph.edges.map((edge) => edge.id)).toEqual(['x-1->x-2', 'x-2->x-3']);
  });

  it('a goal as the root shows only that goal, without the Unfiled group', () => {
    const graph = buildGraph(sampleTree(), { ...OPTIONS, focusKey: 'x-1' });
    expect(graph.nodes.map((node) => node.id)).toEqual(['x-1', 'x-2', 'x-3']);
  });

  it('carries the hidden-done and decision counts on item nodes', () => {
    const graph = buildGraph(sampleTree(), {
      ...OPTIONS,
      decisionCounts: new Map([['x-1', 2]]),
    });
    const goal = graph.nodes.find((node) => node.id === 'x-1');
    const batch = graph.nodes.find((node) => node.id === 'x-2');
    expect(goal?.data).toMatchObject({ decisions: 2 });
    expect(batch?.data).toMatchObject({ hiddenDone: 1, decisions: 0 });
  });

  it('in focus mode shows only the subtree, rooted at the focus', () => {
    const graph = buildGraph(sampleTree(), { ...OPTIONS, focusKey: 'x-2' });
    expect(graph.nodes.map((node) => node.id)).toEqual(['x-2', 'x-3']);
    expect(graph.edges.map((edge) => edge.id)).toEqual(['x-2->x-3']);
    expect(graph.focusMissing).toBe(false);
  });

  it('flags a focus key that is not in the tree', () => {
    const graph = buildGraph(sampleTree(), { ...OPTIONS, focusKey: 'x-99' });
    expect(graph.nodes).toEqual([]);
    expect(graph.focusMissing).toBe(true);
  });
});

describe('overlay', () => {
  it('does nothing without a selected session', () => {
    expect(overlay('x-1', null)).toEqual({ highlighted: false, dimmed: false });
  });

  it('highlights linked items and dims the rest', () => {
    const linked = new Set(['x-3']);
    expect(overlay('x-3', linked)).toEqual({ highlighted: true, dimmed: false });
    expect(overlay('x-1', linked)).toEqual({ highlighted: false, dimmed: true });
  });

  it('applies to every graph node, the Unfiled group dimmed too', () => {
    const graph = buildGraph(sampleTree(), { ...OPTIONS, highlight: new Set(['x-3']) });
    const state = Object.fromEntries(
      graph.nodes.map((node) => [node.id, node.data.dimmed] as const),
    );
    expect(state).toEqual({
      'x-1': true,
      'x-2': true,
      'x-3': false,
      'x-7': true,
      unfiled: true,
    });
  });
});

describe('countByScope', () => {
  it('counts decisions per scope item and skips unscoped ones', () => {
    const counts = countByScope([{ scope: 'x-1' }, { scope: 'x-1' }, { scope: null }]);
    expect([...counts]).toEqual([['x-1', 2]]);
  });
});
