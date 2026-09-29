import { describe, expect, it } from 'vitest';

import { decisionsView } from '../test/api.ts';
import {
  decisionGoals,
  decisionGroups,
  supersededBy,
  type DecisionFilter,
} from './decisionGroups.ts';

const ALL: DecisionFilter = { goal: null, level: null, status: null };

function keys(filter: DecisionFilter): string[][] {
  return decisionGroups(decisionsView().decisions, filter).map((group) =>
    group.decisions.map((d) => d.key),
  );
}

describe('decisionGroups', () => {
  it('groups by goal, in key order, keeping newest first inside', () => {
    const groups = decisionGroups(decisionsView().decisions, ALL);
    expect(groups.map((group) => group.goal)).toEqual(['goal-1', 'goal-2']);
    expect(keys(ALL)).toEqual([
      ['goal-1/batch-1/decision-2', 'goal-1/decision-1'],
      ['goal-2/batch-1/subtask-1/decision-1'],
    ]);
  });

  it('filters by goal, by owner level and by status', () => {
    expect(keys({ ...ALL, goal: 'goal-2' })).toEqual([
      ['goal-2/batch-1/subtask-1/decision-1'],
    ]);
    expect(keys({ ...ALL, level: 'goal' })).toEqual([['goal-1/decision-1']]);
    expect(keys({ ...ALL, level: 'batch' })).toEqual([['goal-1/batch-1/decision-2']]);
    expect(keys({ ...ALL, level: 'subtask', goal: 'goal-1' })).toEqual([]);
    expect(keys({ ...ALL, status: 'superseded' })).toEqual([['goal-1/decision-1']]);
  });

  it('lists the goals for the filter and who supersedes whom', () => {
    const { decisions } = decisionsView();
    expect(decisionGoals(decisions)).toEqual(['goal-1', 'goal-2']);
    expect(supersededBy(decisions).get('goal-1/decision-1')).toBe(
      'goal-1/batch-1/decision-2',
    );
  });
});
