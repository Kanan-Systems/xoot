import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

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
  it("invalidates the project's views, items and decisions only", async () => {
    const client = new QueryClient();
    const seeded = [
      queryKeys.tree('x'),
      queryKeys.backlog('x'),
      queryKeys.decisions('x'),
      queryKeys.item('x', 'goal-1/batch-1'),
      queryKeys.decision('x', 'goal-1/decision-1'),
      queryKeys.changes('x'),
      queryKeys.tree('other'),
      queryKeys.projects(),
    ];
    for (const key of seeded) {
      client.setQueryData(key, { ok: true });
    }
    await invalidateProject(client, 'x');
    const stale = seeded.filter(
      (key) => client.getQueryState(key)?.isInvalidated === true,
    );
    expect(stale.map((key) => key.join('|'))).toEqual([
      'project|x|tree',
      'project|x|backlog',
      'project|x|decisions',
      'project|x|item|goal-1/batch-1',
      'project|x|decision|goal-1/decision-1',
    ]);
  });
});
