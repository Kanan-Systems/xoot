import { describe, expect, it } from 'vitest';

import { sampleTree } from '../test/fixtures.ts';
import { applySessionFilter } from './sessionFilter.ts';

function keys(entries: readonly { item: { key: string } }[]): string[] {
  return entries.map((entry) => entry.item.key);
}

describe('applySessionFilter', () => {
  it('without a filter keeps everything and highlights nothing', () => {
    const result = applySessionFilter(sampleTree(), null);
    expect(keys(result.entries)).toHaveLength(8);
    expect(result.highlight).toBeNull();
  });

  it('highlight mode keeps every item and marks the linked ones', () => {
    const linked = new Set(['x-3', 'x-7']);
    const result = applySessionFilter(sampleTree(), { linked, mode: 'highlight' });
    expect(keys(result.entries)).toEqual(keys(sampleTree()));
    expect(result.highlight).toBe(linked);
  });

  it('only mode keeps the linked items and their ancestors, in tree order', () => {
    const linked = new Set(['x-3', 'x-6', 'x-7']);
    const result = applySessionFilter(sampleTree(), { linked, mode: 'only' });
    // x-3 brings x-2 and x-1; x-6 brings x-5; x-7 is unfiled, alone.
    expect(keys(result.entries)).toEqual(['x-1', 'x-2', 'x-3', 'x-5', 'x-6', 'x-7']);
    expect(result.highlight).toBe(linked);
  });

  it('only mode with a linked key missing from the tree keeps nothing for it', () => {
    const result = applySessionFilter(sampleTree(), {
      linked: new Set(['x-99']),
      mode: 'only',
    });
    expect(result.entries).toEqual([]);
  });
});
