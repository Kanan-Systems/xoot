import { describe, expect, it } from 'vitest';

import { decisionsView, sessionsView, treeView } from '../test/api.ts';
import { labelOf, titleIndex } from './titles.ts';

describe('titleIndex', () => {
  it('knows items, sessions and decisions by key', () => {
    const titles = titleIndex(treeView(), sessionsView(), decisionsView());
    expect(titles.get('x-2')).toBe('title of x-2');
    expect(titles.get('x-S1')).toBe('closed one');
    expect(titles.get('x-D1')).toBe('old rule');
  });

  it('is empty until the queries load', () => {
    expect(titleIndex(undefined, undefined, undefined).size).toBe(0);
  });
});

describe('labelOf', () => {
  it('is "title (key)", or the key alone when the title is unknown', () => {
    const titles = new Map([['x-S1', 'closed one']]);
    expect(labelOf('x-S1', titles)).toBe('closed one (x-S1)');
    expect(labelOf('x-S9', titles)).toBe('x-S9');
  });
});
