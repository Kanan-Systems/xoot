import { describe, expect, it } from 'vitest';

import { B1, B2, G1, G2, item, S3, sampleTree } from '../test/fixtures.ts';
import {
  childKindOf,
  coverChoice,
  decisionOwners,
  isMovable,
  moveTargets,
  optionLabel,
} from './itemRules.ts';

const batch = item(B2, 'batch', G1);
const subtask = item(S3, 'subtask', B2);
const keys = (list: { key: string }[]) => list.map((entry) => entry.key);

describe('the hierarchy in the UI', () => {
  it('offers the child kind and moves only batches and subtasks', () => {
    expect(childKindOf('goal')).toBe('batch');
    expect(childKindOf('batch')).toBe('subtask');
    expect(childKindOf('subtask')).toBeNull();
    expect(childKindOf('backlog')).toBeNull();
    expect(
      ['goal', 'batch', 'subtask', 'backlog'].map((k) => isMovable(k as never)),
    ).toEqual([false, true, true, false]);
  });

  it('moves a batch to another goal and a subtask to another batch', () => {
    expect(keys(moveTargets(batch, sampleTree()))).toEqual([G2]);
    expect(keys(moveTargets(subtask, sampleTree()))).toEqual([B1, 'goal-2/batch-1']);
    expect(moveTargets(item(G1, 'goal', null), sampleTree())).toEqual([]);
  });

  it('cuts long titles in picker options so a select stays narrow', () => {
    const long = { ...batch, title: 'x'.repeat(150) };
    const label = optionLabel(long);
    expect(label).toMatch(/^x{59}… \(goal-1\/batch-2, open\)$/);
  });

  it('offers decisions on goals, batches and subtasks only', () => {
    expect(decisionOwners(sampleTree()).some((i) => i.kind === 'backlog')).toBe(false);
  });
});

describe('coverChoice', () => {
  it('follows the level rule', () => {
    const tree = sampleTree();
    expect(coverChoice({ level: 'batch', parent: B1 }, tree)).toEqual({
      batches: tree
        .map((e) => e.item)
        .filter((i) => i.kind === 'batch' && i.parent === G1),
      ownBatch: B1,
    });
    expect(keys(coverChoice({ level: 'goal', parent: G1 }, tree).batches)).toEqual([
      B1,
      B2,
    ]);
    expect(coverChoice({ level: 'goal', parent: G1 }, tree).ownBatch).toBeNull();
    expect(keys(coverChoice({ level: 'project', parent: null }, tree).batches)).toEqual(
      [B1, B2, 'goal-2/batch-1'],
    );
  });
});
