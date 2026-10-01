import { describe, expect, it } from 'vitest';

import type { ItemSummary } from '../api/types.gen.ts';
import { B1, B2, G1, G2, item, S3 } from '../test/fixtures.ts';
import { dropTarget, NO_TARGET, overlapArea, type Placed } from './dropTarget.ts';

const W = 200;
const H = 60;

function at(summary: ItemSummary, x: number, y: number): Placed {
  return { item: summary, rect: { x, y, width: W, height: H } };
}

const goal1 = item(G1, 'goal', null);
const goal2 = item(G2, 'goal', null);
const batch = item(B2, 'batch', G1);
const subtask = item(S3, 'subtask', B2);
// The batch as dropped, at the origin.
const dropped = at(batch, 0, 0);

describe('dropTarget', () => {
  it('measures the overlap of two rectangles, zero when they only touch', () => {
    expect(overlapArea(dropped.rect, at(goal2, 100, 30).rect)).toBe(100 * 30);
    expect(overlapArea(dropped.rect, at(goal2, W, 0).rect)).toBe(0);
  });

  it('finds no target far away', () => {
    expect(dropTarget(dropped, [at(goal2, 900, 900)])).toEqual({
      ok: false,
      reason: NO_TARGET,
    });
  });

  it('finds no target when the nodes barely touch', () => {
    // A 4px graze of the corner: xyflow counts it, a drop must not.
    expect(dropTarget(dropped, [at(goal2, W - 4, H - 4)])).toEqual({
      ok: false,
      reason: NO_TARGET,
    });
  });

  it('takes a target that clearly overlaps', () => {
    expect(dropTarget(dropped, [at(goal2, 40, 10)])).toEqual({ ok: true, parent: G2 });
    expect(dropTarget(at(subtask, 0, 0), [at(item(B1, 'batch', G1), 20, 5)])).toEqual({
      ok: true,
      parent: B1,
    });
  });

  it('picks the largest overlap of two, whatever their order', () => {
    const small = at(goal1, 120, 0);
    const large = at(goal2, 30, 0);
    expect(dropTarget(dropped, [small, large])).toEqual({ ok: true, parent: G2 });
    expect(dropTarget(dropped, [large, small])).toEqual({ ok: true, parent: G2 });
  });

  it('refuses when the largest overlap is the current parent', () => {
    expect(dropTarget(dropped, [at(goal1, 10, 0), at(goal2, 150, 0)])).toEqual({
      ok: false,
      reason: `${B2} is already there.`,
    });
  });

  it('finds no target of an invalid kind, however large the overlap', () => {
    expect(dropTarget(dropped, [at(item(B1, 'batch', G1), 0, 0)])).toEqual({
      ok: false,
      reason: NO_TARGET,
    });
    expect(dropTarget(at(subtask, 0, 0), [at(goal2, 0, 0)])).toMatchObject({
      ok: false,
    });
  });

  it('never moves goals or backlog items', () => {
    expect(dropTarget(at(goal1, 0, 0), [at(goal2, 0, 0)])).toMatchObject({ ok: false });
    expect(
      dropTarget(at(item('backlog-1', 'backlog', null), 0, 0), [dropped]),
    ).toMatchObject({ ok: false });
  });
});
