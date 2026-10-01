import { describe, expect, it } from 'vitest';

import { resolveProjectName, withProject } from './projectName.ts';

const PROJECTS = [
  { key_prefix: 'kanan', name: 'xoot', aliases: ['xoot', 'xo'] },
  { key_prefix: 'nova', name: 'Nova', aliases: [] },
];

describe('resolveProjectName', () => {
  it('a prefix is the project itself', () => {
    expect(resolveProjectName(PROJECTS, 'nova')).toEqual({ kind: 'prefix' });
  });

  it('an alias names its prefix', () => {
    expect(resolveProjectName(PROJECTS, 'xo')).toEqual({
      kind: 'alias',
      prefix: 'kanan',
    });
  });

  it('a display name alone is not an alias', () => {
    expect(resolveProjectName(PROJECTS, 'Nova')).toEqual({ kind: 'unknown' });
  });
});

describe('withProject', () => {
  it('replaces only the first segment', () => {
    expect(withProject('/xoot', 'kanan')).toBe('/kanan');
    expect(withProject('/xoot/', 'kanan')).toBe('/kanan');
    expect(withProject('/xoot/tree', 'kanan')).toBe('/kanan/tree');
    expect(withProject('/xoot/item/goal-1/batch-2', 'kanan')).toBe(
      '/kanan/item/goal-1/batch-2',
    );
  });
});
