import { describe, expect, it } from 'vitest';

import type { TreeEntry } from '../api/types.gen.ts';
import {
  B1,
  B1_BACKLOG,
  B2,
  entry,
  G1,
  G1_BACKLOG,
  G2,
  item,
  P_BACKLOG,
  sampleTree,
} from '../test/fixtures.ts';
import {
  blockedHint,
  blockedLine,
  buildGraph,
  collapseDone,
  countByOwner,
  PROJECT_ID,
  subtree,
  type GraphOptions,
} from './tree.ts';

const OPTIONS: GraphOptions = {
  showDone: false,
  rootKey: null,
  project: { name: 'Xproj', prefix: 'x' },
  decisionCounts: new Map(),
  blocked: new Map([[B1, 1]]),
};

function ids(entries: readonly { id: string }[]): string[] {
  return entries.map((node) => node.id);
}

describe('buildGraph: the project-root tree', () => {
  it('hangs goals and open project backlog off the project node', () => {
    const graph = buildGraph(sampleTree(), OPTIONS);
    expect(graph.nodes[0]).toMatchObject({ id: PROJECT_ID, type: 'project' });
    const fromProject = graph.edges.filter((edge) => edge.source === PROJECT_ID);
    expect(fromProject.map((edge) => edge.target)).toEqual([G1, P_BACKLOG]);
  });

  it('keeps backlog items under the batch or goal they sit on', () => {
    const graph = buildGraph(sampleTree(), OPTIONS);
    expect(graph.edges).toContainEqual(
      expect.objectContaining({ source: B1, target: B1_BACKLOG }),
    );
    expect(graph.edges).toContainEqual(
      expect.objectContaining({ source: G1, target: G1_BACKLOG }),
    );
  });

  it('counts hidden closed children per category, never as one "done"', () => {
    const graph = buildGraph(sampleTree(), OPTIONS);
    const batch = graph.nodes.find((node) => node.id === B1);
    expect(batch?.data.hidden).toEqual({ done: 1, dropped: 1 });
    const project = graph.nodes.find((node) => node.id === PROJECT_ID);
    expect(project?.data.hidden).toEqual({ done: 2 });
    expect(ids(graph.nodes)).not.toContain(G2);
  });

  it('shows closed items, and what sits under them, with showDone', () => {
    const graph = buildGraph(sampleTree(), { ...OPTIONS, showDone: true });
    expect(ids(graph.nodes)).toEqual([
      PROJECT_ID,
      ...sampleTree().map((e) => e.item.key),
    ]);
  });

  it('marks what open backlog blocks, with the backlog keys', () => {
    const graph = buildGraph(sampleTree(), OPTIONS);
    const batch = graph.nodes.find((node) => node.id === B1);
    expect(batch?.type === 'item' && batch.data.blocked).toEqual({
      count: 1,
      children: 'subtasks',
      backlog: [B1_BACKLOG],
    });
    const other = graph.nodes.find((node) => node.id === B2);
    expect(other?.type === 'item' && other.data.blocked).toBeNull();
  });
});

describe('buildGraph: one goal or a focus root', () => {
  it('narrows to the goal, with no project node', () => {
    const graph = buildGraph(sampleTree(), { ...OPTIONS, rootKey: G1 });
    expect(ids(graph.nodes)).not.toContain(PROJECT_ID);
    expect(ids(graph.nodes)).not.toContain(P_BACKLOG);
    expect(ids(graph.nodes)[0]).toBe(G1);
    expect(graph.edges.some((edge) => edge.target === G1)).toBe(false);
  });

  it('keeps a closed root visible and says when the root is gone', () => {
    const done = buildGraph(sampleTree(), { ...OPTIONS, rootKey: G2 });
    expect(ids(done.nodes)).toEqual([G2]);
    expect(done.rootMissing).toBe(false);
    const gone = buildGraph(sampleTree(), { ...OPTIONS, rootKey: 'goal-9' });
    expect(gone.nodes).toEqual([]);
    expect(gone.rootMissing).toBe(true);
  });
});

describe('helpers', () => {
  it('subtree keeps the root and its descendants', () => {
    expect(subtree(sampleTree(), B2).map((e) => e.item.key)).toEqual([
      B2,
      'goal-1/batch-2/subtask-1',
    ]);
  });

  it('collapseDone hides what sits under a hidden parent without counting it', () => {
    const entries: TreeEntry[] = [
      entry(item(G2, 'goal', null, 'done'), 0),
      entry(item('goal-2/batch-1', 'batch', G2, 'dropped'), 1),
    ];
    const { visible, hidden } = collapseDone(entries, false);
    expect(visible).toEqual([]);
    expect(hidden.get(PROJECT_ID)).toEqual({ done: 1 });
    expect(hidden.has(G2)).toBe(false);
  });

  it('words the blocked line by kind and names the backlog in the hint', () => {
    const blocked = {
      count: 2,
      children: 'batches' as const,
      backlog: ['goal-1/backlog-1'],
    };
    expect(blockedLine(blocked)).toBe('all batches done · 2 backlog open');
    expect(blockedHint(G1, blocked)).toBe(
      'Cover or push goal-1/backlog-1 in the Backlog tab',
    );
    expect(blockedHint(G1, { ...blocked, backlog: [] })).toBe(
      'Cover or push goal-1 in the Backlog tab',
    );
  });

  it('countByOwner counts decisions per owner key', () => {
    expect(countByOwner([{ owner: B1 }, { owner: B1 }, { owner: null }])).toEqual(
      new Map([[B1, 2]]),
    );
  });
});
