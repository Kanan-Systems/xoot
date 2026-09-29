import { describe, expect, it } from 'vitest';

import { ago, CATEGORY, DECISION_STATUS, KIND, KINDS, when } from './display.ts';

describe('ago', () => {
  it('counts seconds, then minutes, then hours', () => {
    expect(ago(0)).toBe('0 s ago');
    expect(ago(59)).toBe('59 s ago');
    expect(ago(60)).toBe('1 min ago');
    expect(ago(3599)).toBe('59 min ago');
    expect(ago(7200)).toBe('2 h ago');
  });
});

describe('glyphs', () => {
  it('every kind, category and decision status has an icon and a label', () => {
    for (const glyph of [
      ...Object.values(KIND),
      ...Object.values(CATEGORY),
      ...Object.values(DECISION_STATUS),
    ]) {
      expect(glyph.icon).not.toBe('');
      expect(glyph.label).not.toBe('');
    }
    expect(KINDS).toEqual(['goal', 'batch', 'subtask', 'backlog']);
    expect(Object.keys(CATEGORY)).toHaveLength(6);
  });

  it('backlog has an icon of its own', () => {
    const others = KINDS.filter((kind) => kind !== 'backlog').map((k) => KIND[k].icon);
    expect(others).not.toContain(KIND.backlog.icon);
  });
});

describe('when', () => {
  it('shows date and minutes', () => {
    expect(when('2026-09-28T09:30:12.000000Z')).toBe('2026-09-28 09:30');
  });
});
