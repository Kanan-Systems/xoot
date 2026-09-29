import { describe, expect, it } from 'vitest';

import { compareKeys, goalOf, keyPath, ownerLevel } from './keys.ts';

describe('keys', () => {
  it('finds the goal a key sits under', () => {
    expect(goalOf('goal-3/batch-1/subtask-2')).toBe('goal-3');
    expect(goalOf('goal-3')).toBe('goal-3');
    expect(goalOf('backlog-4')).toBeNull();
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
