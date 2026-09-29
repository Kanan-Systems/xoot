import { describe, expect, it } from 'vitest';

import type { Disposition, SessionItemEntry } from '../api/types.gen.ts';
import { item } from '../test/fixtures.ts';
import { groupByOutcome, outcomeOf } from './sessionGroups.ts';

function linked(
  key: string,
  disposition: Disposition | null,
  category: 'open' | 'done' | 'dropped' | 'backlogged' = 'open',
): SessionItemEntry {
  return { item: item(key, 'subtask', null, category), disposition, captured: false };
}

describe('groupByOutcome', () => {
  it('groups a closed session by disposition, done and dropped first', () => {
    const groups = groupByOutcome(
      [
        linked('x-1', 'carry_over'),
        linked('x-2', null, 'done'),
        linked('x-3', 'session_backlog', 'backlogged'),
        linked('x-4', 'dropped', 'dropped'),
        linked('x-5', null, 'dropped'),
        linked('x-6', 'project_backlog', 'backlogged'),
        linked('x-7', 'carry_over'),
      ],
      'closed',
    );
    expect(groups.map((g) => [g.outcome, g.entries.map((e) => e.item.key)])).toEqual([
      ['done', ['x-2']],
      ['dropped', ['x-5']],
      ['carry_over', ['x-1', 'x-7']],
      ['session_backlog', ['x-3']],
      ['project_backlog', ['x-6']],
      ['dropped_at_close', ['x-4']],
    ]);
    expect(groups[2]?.label).toBe('Carried over');
  });

  it('in an open session, an open item with no disposition is in progress', () => {
    expect(outcomeOf(linked('x-1', null), 'open')).toBe('in_progress');
  });

  it('in a closed session, an open item with no disposition is flagged', () => {
    expect(outcomeOf(linked('x-1', null), 'closed')).toBe('unresolved');
  });

  it('drops empty groups', () => {
    expect(groupByOutcome([], 'closed')).toEqual([]);
  });
});
