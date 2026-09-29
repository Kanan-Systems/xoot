import { describe, expect, it } from 'vitest';

import { backlogsView } from '../test/api.ts';
import { backlogGroups } from './backlogGroups.ts';

describe('backlogGroups', () => {
  it('lists each open session, then the project backlog, then unfiled', () => {
    const groups = backlogGroups(backlogsView());
    expect(groups.map((group) => [group.heading, group.key])).toEqual([
      ['open one', 'x-S2'],
      ['Project backlog', null],
      ['Unfiled', null],
    ]);
    expect(groups.map((group) => group.items.map((row) => row.key))).toEqual([
      ['x-9'],
      ['x-10'],
      ['x-9', 'x-7'],
    ]);
  });

  it('skips a session that is no longer open', () => {
    const view = backlogsView();
    const [first] = view.sessions;
    if (first === undefined) {
      throw new Error('fixture has a session');
    }
    view.sessions = [{ ...first, session: { ...first.session, status: 'closed' } }];
    expect(backlogGroups(view).map((group) => group.id)).toEqual([
      'project',
      'unfiled',
    ]);
  });
});
