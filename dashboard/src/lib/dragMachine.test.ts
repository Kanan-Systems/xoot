import { describe, expect, it } from 'vitest';

import { B1, B2, G1, G1_BACKLOG, G2, item, S3 } from '../test/fixtures.ts';
import { dragReducer, IDLE, type DragEvent, type DragState } from './dragMachine.ts';

const batch = item(B2, 'batch', G1);
const subtask = item(S3, 'subtask', B2);

function run(...events: DragEvent[]): DragState {
  return events.reduce(dragReducer, IDLE);
}

describe('the armed-drag state machine', () => {
  it('arms a batch or a subtask on double-click', () => {
    expect(run({ type: 'arm', item: batch })).toEqual({ armed: B2, pending: null });
    expect(run({ type: 'arm', item: subtask })).toEqual({ armed: S3, pending: null });
  });

  it('never arms a goal or a backlog item', () => {
    expect(run({ type: 'arm', item: item(G1, 'goal', null) })).toBe(IDLE);
    expect(run({ type: 'arm', item: item(G1_BACKLOG, 'backlog', G1) })).toBe(IDLE);
  });

  it('keeps one armed node at a time: arming another replaces it', () => {
    expect(run({ type: 'arm', item: batch }, { type: 'arm', item: subtask })).toEqual({
      armed: S3,
      pending: null,
    });
  });

  it('disarms on Escape or a click on empty canvas', () => {
    expect(run({ type: 'arm', item: batch }, { type: 'disarm' })).toBe(IDLE);
  });

  it('only a drop of the armed node waits for confirmation', () => {
    expect(run({ type: 'drop', item: batch, parent: G2 })).toBe(IDLE);
    expect(
      run({ type: 'arm', item: subtask }, { type: 'drop', item: batch, parent: G2 }),
    ).toEqual({ armed: S3, pending: null });
    expect(
      run({ type: 'arm', item: batch }, { type: 'drop', item: batch, parent: G2 }),
    ).toEqual({ armed: B2, pending: { item: batch, parent: G2 } });
  });

  it('does not re-arm or take a second drop while a move waits', () => {
    const waiting = run(
      { type: 'arm', item: batch },
      { type: 'drop', item: batch, parent: G2 },
    );
    expect(dragReducer(waiting, { type: 'arm', item: subtask })).toBe(waiting);
    expect(dragReducer(waiting, { type: 'drop', item: batch, parent: B1 })).toBe(
      waiting,
    );
  });

  it('ends the move on Confirm, Cancel or Escape', () => {
    const waiting = run(
      { type: 'arm', item: batch },
      { type: 'drop', item: batch, parent: G2 },
    );
    expect(dragReducer(waiting, { type: 'confirm' })).toBe(IDLE);
    expect(dragReducer(waiting, { type: 'cancel' })).toBe(IDLE);
    expect(dragReducer(waiting, { type: 'disarm' })).toBe(IDLE);
  });
});
