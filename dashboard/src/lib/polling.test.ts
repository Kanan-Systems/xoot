import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';

import { changed, invalidateProject, queryKeys } from './polling.ts';

describe('changed', () => {
  it('treats the first reading as a baseline', () => {
    expect(changed(undefined, 5)).toBe(false);
  });

  it('reports a moved id and ignores an unchanged or missing one', () => {
    expect(changed(5, 6)).toBe(true);
    expect(changed(5, 5)).toBe(false);
    expect(changed(5, undefined)).toBe(false);
  });
});

describe('invalidateProject', () => {
  it('invalidates the project, items and decisions but not /changes or others', async () => {
    const client = new QueryClient();
    const seeded = [
      queryKeys.tree('x'),
      queryKeys.brief('x'),
      queryKeys.session('x', 'x-S1'),
      queryKeys.item('x-1'),
      queryKeys.decision('x-D1'),
      queryKeys.changes('x'),
      queryKeys.tree('other'),
      queryKeys.projects(),
    ];
    for (const key of seeded) {
      client.setQueryData(key, { ok: true });
    }
    const spy = vi.spyOn(client, 'invalidateQueries');
    await invalidateProject(client, 'x');
    const stale = seeded.filter(
      (key) => client.getQueryState(key)?.isInvalidated === true,
    );
    expect(stale.map((key) => key.join('/'))).toEqual([
      'project/x/tree',
      'project/x/brief',
      'project/x/session/x-S1',
      'item/x-1',
      'decision/x-D1',
    ]);
    expect(spy).toHaveBeenCalledTimes(3);
  });
});
