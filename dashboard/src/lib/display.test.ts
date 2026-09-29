import { describe, expect, it } from 'vitest';

import { ago, CATEGORY, DECISION_STATUS } from './display.ts';

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
  it('every category and decision status has an icon and a label', () => {
    for (const glyph of [
      ...Object.values(CATEGORY),
      ...Object.values(DECISION_STATUS),
    ]) {
      expect(glyph.icon).not.toBe('');
      expect(glyph.label).not.toBe('');
    }
    expect(Object.keys(CATEGORY)).toHaveLength(7);
  });
});
