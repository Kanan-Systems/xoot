import { describe, expect, it } from 'vitest';

import { decisionsView, treeView } from '../test/api.ts';
import { B1 } from '../test/fixtures.ts';
import { labelOf, titleIndex } from './titles.ts';

describe('titleIndex', () => {
  it('knows items and decisions by key', () => {
    const titles = titleIndex(treeView(), decisionsView());
    expect(titles.get(B1)).toBe(`title of ${B1}`);
    expect(titles.get('goal-1/decision-1')).toBe('old rule');
  });

  it('is empty until the queries load', () => {
    expect(titleIndex(undefined, undefined).size).toBe(0);
  });
});

describe('labelOf', () => {
  it('is "title (key)", or the key alone when the title is unknown', () => {
    const titles = new Map([['goal-1', 'Ship']]);
    expect(labelOf('goal-1', titles)).toBe('Ship (goal-1)');
    expect(labelOf('goal-9', titles)).toBe('goal-9');
  });
});
