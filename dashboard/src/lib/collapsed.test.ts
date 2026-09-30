import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { loadCollapsed, pruned, saveCollapsed, storageKey } from './collapsed.ts';

describe('collapsed storage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('saves and loads per project', () => {
    saveCollapsed('x', new Set(['goal-2', 'goal-1/batch-1']));
    expect(loadCollapsed('x')).toEqual(new Set(['goal-2', 'goal-1/batch-1']));
    expect(loadCollapsed('y')).toEqual(new Set());
  });

  it('stores only the sorted key list, and removes it when empty', () => {
    saveCollapsed('x', new Set(['goal-2', 'goal-1']));
    expect(localStorage.getItem(storageKey('x'))).toBe('["goal-1","goal-2"]');
    saveCollapsed('x', new Set());
    expect(localStorage.getItem(storageKey('x'))).toBeNull();
  });

  it.each(['{not json', '"goal-1"', '{"goal-1":true}', 'null', '42'])(
    'reads garbage %j as nothing collapsed',
    (raw) => {
      localStorage.setItem(storageKey('x'), raw);
      expect(loadCollapsed('x')).toEqual(new Set());
    },
  );

  it('keeps only the strings of a mixed list', () => {
    localStorage.setItem(storageKey('x'), '["goal-1", 3, null, {"a": 1}]');
    expect(loadCollapsed('x')).toEqual(new Set(['goal-1']));
  });

  it('survives storage that throws on read and write', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota');
    });
    expect(loadCollapsed('x')).toEqual(new Set());
    expect(() => {
      saveCollapsed('x', new Set(['goal-1']));
    }).not.toThrow();
  });

  it('survives a window whose localStorage getter throws', () => {
    vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {
      throw new Error('denied');
    });
    expect(loadCollapsed('x')).toEqual(new Set());
    expect(() => {
      saveCollapsed('x', new Set(['goal-1']));
    }).not.toThrow();
  });

  it('keeps each view under its own key', () => {
    saveCollapsed('x', new Set(['goal-1']), 'decisions');
    expect(localStorage.getItem(storageKey('x', 'decisions'))).toBe('["goal-1"]');
    expect(loadCollapsed('x')).toEqual(new Set());
    expect(loadCollapsed('x', 'decisions')).toEqual(new Set(['goal-1']));
  });

  it('prunes only keys that no longer exist, and says when none go', () => {
    const existing = new Set(['goal-1', 'goal-1/batch-1']);
    expect(pruned(new Set(['goal-1', 'goal-9']), existing)).toEqual(
      new Set(['goal-1']),
    );
    expect(pruned(new Set(['goal-1']), existing)).toBeNull();
    expect(pruned(new Set(), existing)).toBeNull();
  });
});
