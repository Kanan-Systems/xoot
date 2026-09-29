import { describe, expect, it } from 'vitest';

import { backlogView } from '../test/api.ts';
import { B1, B1_BACKLOG, G1, G1_BACKLOG, P_BACKLOG } from '../test/fixtures.ts';
import { backlogGroups } from './backlogGroups.ts';

const TITLES = new Map([
  [G1, 'Ship export'],
  [B1, 'Writer'],
]);

describe('backlogGroups', () => {
  it('orders batch backlog, then goal backlog, then the project backlog', () => {
    const groups = backlogGroups(backlogView(), TITLES);
    expect(groups.map((group) => group.level)).toEqual(['batch', 'goal', 'project']);
    expect(groups.map((group) => group.items.map((row) => row.key))).toEqual([
      [B1_BACKLOG],
      [G1_BACKLOG],
      [P_BACKLOG],
    ]);
  });

  it('heads a batch group with its goal and batch titles, keys second', () => {
    const [batch, goal, project] = backlogGroups(backlogView(), TITLES);
    expect(batch?.holders).toEqual([
      { key: G1, title: 'Ship export' },
      { key: B1, title: 'Writer' },
    ]);
    expect(goal?.holders).toEqual([{ key: G1, title: 'Ship export' }]);
    expect(project?.holders).toEqual([]);
  });

  it('sorts groups of one level by key, naturally', () => {
    const view = backlogView();
    const base = view.items[1];
    if (base === undefined) {
      throw new Error('fixture has a goal row');
    }
    view.items = [
      { ...base, key: 'goal-10/backlog-1', parent: 'goal-10' },
      { ...base, key: 'goal-2/backlog-1', parent: 'goal-2' },
    ];
    expect(backlogGroups(view, TITLES).map((group) => group.id)).toEqual([
      'goal:goal-2',
      'goal:goal-10',
    ]);
  });
});
