import { describe, expect, it } from 'vitest';

import {
  batchOf,
  compareKeys,
  goalOf,
  keyPath,
  ownerLevel,
  subtaskOf,
} from './keys.ts';

describe('keys', () => {
  it('finds the goal a key sits under', () => {
    expect(goalOf('goal-3/batch-1/subtask-2')).toBe('goal-3');
    expect(goalOf('goal-3')).toBe('goal-3');
    expect(goalOf('backlog-4')).toBeNull();
  });

  it('finds the batch and subtask a key sits under', () => {
    expect(batchOf('goal-3/batch-1/subtask-2/decision-1')).toBe('goal-3/batch-1');
    expect(batchOf('goal-3/batch-1')).toBe('goal-3/batch-1');
    expect(batchOf('goal-3')).toBeNull();
    expect(batchOf('goal-3/backlog-1')).toBeNull();
    expect(batchOf('backlog-1/batch-2')).toBeNull();
    expect(subtaskOf('goal-3/batch-1/subtask-2/decision-1')).toBe(
      'goal-3/batch-1/subtask-2',
    );
    expect(subtaskOf('goal-3/batch-1/subtask-2')).toBe('goal-3/batch-1/subtask-2');
    expect(subtaskOf('goal-3/batch-1')).toBeNull();
    expect(subtaskOf('goal-3/batch-1/backlog-2')).toBeNull();
  });

  it('reads an owner level from the last segment', () => {
    expect(ownerLevel('goal-1')).toBe('goal');
    expect(ownerLevel('goal-1/batch-2')).toBe('batch');
    expect(ownerLevel('goal-1/batch-2/subtask-10')).toBe('subtask');
    expect(ownerLevel('goal-1/backlog-1')).toBeNull();
  });

  it('sorts numbers naturally', () => {
    expect(['goal-10', 'goal-2', 'goal-1'].sort(compareKeys)).toEqual([
      'goal-1',
      'goal-2',
      'goal-10',
    ]);
  });

  it('encodes each segment and keeps the slashes', () => {
    expect(keyPath('goal-1/batch-2')).toBe('goal-1/batch-2');
    expect(keyPath('a b/c?d')).toBe('a%20b/c%3Fd');
  });
});
