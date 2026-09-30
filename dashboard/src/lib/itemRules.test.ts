import { describe, expect, it } from 'vitest';

import { B1, B2, G1, G2, item, S3, sampleTree } from '../test/fixtures.ts';
import {
  childKindOf,
  coverChoice,
  decisionOwners,
  dropTarget,
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

describe('dropTarget', () => {
  it('takes a batch dropped on a goal and a subtask dropped on a batch', () => {
    expect(dropTarget(batch, [item(G2, 'goal', null)])).toEqual({
      ok: true,
      parent: G2,
    });
    expect(dropTarget(subtask, [item(B1, 'batch', G1)])).toEqual({
      ok: true,
      parent: B1,
    });
  });

  it('skips nodes of the wrong kind and picks the first fitting one', () => {
    const hits = [
      item(S3, 'subtask', B2),
      item(B1, 'batch', G1),
      item(G2, 'goal', null),
    ];
    expect(dropTarget(batch, hits)).toEqual({ ok: true, parent: G2 });
  });

  it('refuses the current parent', () => {
    expect(dropTarget(batch, [item(G1, 'goal', null)])).toEqual({
      ok: false,
      reason: `${B2} is already there.`,
    });
  });

  it('refuses a drop on nothing or on the wrong kind', () => {
    const refused = {
      ok: false,
      reason: expect.stringMatching(/onto a goal/) as unknown,
    };
    expect(dropTarget(batch, [])).toEqual(refused);
    expect(dropTarget(batch, [item(B1, 'batch', G1)])).toEqual(refused);
    expect(dropTarget(subtask, [item(G2, 'goal', null)])).toMatchObject({ ok: false });
  });

  it('never moves goals or backlog items', () => {
    expect(dropTarget(item(G1, 'goal', null), [item(G2, 'goal', null)])).toMatchObject({
      ok: false,
    });
    expect(dropTarget(item('backlog-1', 'backlog', null), [batch])).toMatchObject({
      ok: false,
    });
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
