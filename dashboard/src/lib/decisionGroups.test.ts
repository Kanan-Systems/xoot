import { describe, expect, it } from 'vitest';

import type { DecisionSummary } from '../api/types.gen.ts';
import { decisionsView } from '../test/api.ts';
import {
  countOf,
  decisionGoals,
  decisionHierarchy,
  supersededBy,
  type DecisionFilter,
  type DecisionNode,
} from './decisionGroups.ts';

const ALL: DecisionFilter = { goal: null, level: null, status: null };

// Each heading as "key: its decisions", depth first.
function outline(nodes: readonly DecisionNode[], indent = ''): string[] {
  return nodes.flatMap((node) => [
    `${indent}${node.key}: ${node.decisions.map((d) => d.key).join(', ')}`,
    ...outline(node.children, `${indent}  `),
  ]);
}

function tree(filter: DecisionFilter): string[] {
  return outline(decisionHierarchy(decisionsView().decisions, filter).goals);
}

describe('decisionHierarchy', () => {
  it('groups goal > batch > subtask, the goal decisions under the goal', () => {
    expect(tree(ALL)).toEqual([
      'goal-1: goal-1/decision-1',
      '  goal-1/batch-1: goal-1/batch-1/decision-2',
      'goal-2: ',
      '  goal-2/batch-1: ',
      '    goal-2/batch-1/subtask-1: goal-2/batch-1/subtask-1/decision-1',
    ]);
  });

  it('sorts headings naturally and keeps the API order inside one', () => {
    const base = {
      supersedes: null,
      updated_at: 't',
      version: 1,
      status: 'locked' as const,
    };
    const decisions: DecisionSummary[] = [
      { ...base, key: 'goal-10/decision-2', title: 'b', owner: 'goal-10' },
      { ...base, key: 'goal-10/decision-1', title: 'a', owner: 'goal-10' },
      { ...base, key: 'goal-2/decision-1', title: 'c', owner: 'goal-2' },
    ];
    expect(outline(decisionHierarchy(decisions, ALL).goals)).toEqual([
      'goal-2: goal-2/decision-1',
      'goal-10: goal-10/decision-2, goal-10/decision-1',
    ]);
  });

  it('puts decisions whose owner is gone in their own list', () => {
    const [first] = decisionsView().decisions;
    if (first === undefined) {
      throw new Error('fixture');
    }
    const gone = { ...first, key: 'goal-9/decision-1', owner: null };
    const hierarchy = decisionHierarchy([gone], ALL);
    expect(hierarchy.goals).toEqual([]);
    expect(hierarchy.ownerless.map((d) => d.key)).toEqual(['goal-9/decision-1']);
  });

  it('filters by goal, by owner level and by status, dropping empty headings', () => {
    expect(tree({ ...ALL, goal: 'goal-2' })).toEqual([
      'goal-2: ',
      '  goal-2/batch-1: ',
      '    goal-2/batch-1/subtask-1: goal-2/batch-1/subtask-1/decision-1',
    ]);
    expect(tree({ ...ALL, level: 'goal' })).toEqual(['goal-1: goal-1/decision-1']);
    expect(tree({ ...ALL, level: 'batch' })).toEqual([
      'goal-1: ',
      '  goal-1/batch-1: goal-1/batch-1/decision-2',
    ]);
    expect(tree({ ...ALL, level: 'subtask', goal: 'goal-1' })).toEqual([]);
    expect(tree({ ...ALL, status: 'superseded' })).toEqual([
      'goal-1: goal-1/decision-1',
    ]);
  });

  it('counts the decisions at and below a heading', () => {
    const { goals } = decisionHierarchy(decisionsView().decisions, ALL);
    expect(goals.map(countOf)).toEqual([2, 1]);
  });

  it('lists the goals for the filter and who supersedes whom', () => {
    const { decisions } = decisionsView();
    expect(decisionGoals(decisions)).toEqual(['goal-1', 'goal-2']);
    expect(supersededBy(decisions).get('goal-1/decision-1')).toBe(
      'goal-1/batch-1/decision-2',
    );
  });
});
