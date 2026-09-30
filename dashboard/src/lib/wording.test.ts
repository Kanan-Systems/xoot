import { describe, expect, it } from 'vitest';

import type { SubtreeOutput } from '../api/types.gen.ts';
import { sampleTree } from '../test/fixtures.ts';
import {
  countsText,
  descendants,
  dropPlanText,
  dropResultText,
  kindOf,
  moveFactsFromPlan,
  movePlanText,
  moveResultText,
  pushPlanText,
  pushResultText,
} from './wording.ts';

const TITLES = new Map([
  ['goal-1', 'Ship export'],
  ['goal-2', 'Import'],
  ['goal-1/batch-1', 'Writer'],
  ['goal-2/batch-2', 'Reader'],
  ['goal-2/batch-1', 'Parser'],
  ['goal-2/batch-1/subtask-1', 'Parse rows'],
  ['goal-1/batch-1/backlog-1', 'Flaky test'],
]);

const plan = (root: string, changes: SubtreeOutput['changes']): SubtreeOutput => ({
  root,
  changes,
});

describe('plain-language wording', () => {
  it('reads kinds from keys and counts in words', () => {
    expect(kindOf('goal-1/batch-2/backlog-3')).toBe('backlog');
    expect(kindOf('x-1')).toBeNull();
    expect(countsText({ subtask: 1 })).toBe('1 subtask');
    expect(countsText({ batch: 2, subtask: 3, backlog: 1 })).toBe(
      '2 batches, 3 subtasks and 1 backlog item',
    );
    expect(countsText({})).toBe('');
  });

  it('words a push before and after', () => {
    const push = plan('goal-1/batch-1/backlog-1', [
      {
        key: 'goal-1/batch-1/backlog-1',
        before: {
          key: 'goal-1/batch-1/backlog-1',
          parent: 'goal-1/batch-1',
          number: 1,
        },
        after: { key: 'goal-1/backlog-4', parent: 'goal-1', number: 4 },
      },
    ]);
    expect(pushPlanText('goal-1/batch-1/backlog-1', push, TITLES)).toBe(
      "Move backlog item 'Flaky test' up from batch 'Writer' to goal 'Ship export'. " +
        "It will be listed in the backlog of goal 'Ship export'.",
    );
    expect(pushResultText('goal-1/batch-1/backlog-1', push, TITLES)).toBe(
      "Moved backlog item 'Flaky test' up to goal 'Ship export'. " +
        "It is now listed in the backlog of goal 'Ship export'.",
    );
  });

  it('words a push to the project', () => {
    const titles = new Map([...TITLES, ['goal-1/backlog-4', 'Docs']]);
    const push = plan('goal-1/backlog-4', [
      {
        key: 'goal-1/backlog-4',
        before: { key: 'goal-1/backlog-4', parent: 'goal-1' },
        after: { key: 'backlog-2', parent: null },
      },
    ]);
    expect(pushPlanText('goal-1/backlog-4', push, titles)).toBe(
      "Move backlog item 'Docs' up from goal 'Ship export' to the project. " +
        'It will be listed in the project backlog.',
    );
  });

  it('words a move with its new key and what moves along', () => {
    const move = plan('goal-2/batch-1', [
      {
        key: 'goal-2/batch-1',
        before: { key: 'goal-2/batch-1', parent: 'goal-2' },
        after: { key: 'goal-1/batch-2', parent: 'goal-1' },
      },
      {
        key: 'goal-2/batch-1/subtask-1',
        before: { key: 'goal-2/batch-1/subtask-1' },
        after: { key: 'goal-1/batch-2/subtask-1' },
      },
    ]);
    const facts = moveFactsFromPlan('goal-2/batch-1', 'goal-1', move);
    expect(movePlanText(facts, TITLES)).toBe(
      "Move batch 'Parser' from goal 'Import' to goal 'Ship export'. " +
        'Its key will change to goal-1/batch-2. Its 1 subtask moves with it.',
    );
    expect(moveResultText(facts, TITLES)).toBe(
      "Moved batch 'Parser' to goal 'Ship export'. Its key is now goal-1/batch-2.",
    );
  });

  it('names the goal of a batch when a subtask moves, before its key is known', () => {
    const facts = {
      key: 'goal-2/batch-1/subtask-1',
      parent: 'goal-1/batch-1',
      newKey: null,
      children: {},
    };
    expect(movePlanText(facts, TITLES)).toBe(
      "Move subtask 'Parse rows' from batch 'Parser' (goal 'Import') " +
        "to batch 'Writer' (goal 'Ship export').",
    );
  });

  it('words a drop with its open children', () => {
    const drop = plan('goal-2/batch-2', [
      {
        key: 'goal-2/batch-2/subtask-1',
        before: { state: 'open' },
        after: { state: 'dropped' },
      },
      {
        key: 'goal-2/batch-2/subtask-2',
        before: { state: 'open' },
        after: { state: 'dropped' },
      },
      { key: 'goal-2/batch-2', before: { state: 'open' }, after: { state: 'dropped' } },
    ]);
    expect(dropPlanText('goal-2/batch-2', drop, TITLES)).toBe(
      "Drop batch 'Reader' and its 2 open subtasks.",
    );
    expect(dropResultText('goal-2/batch-2', drop, TITLES)).toBe(
      "Dropped batch 'Reader' and its 2 open subtasks.",
    );
  });

  it('falls back (null) when a title is unknown', () => {
    const unknown = plan('goal-9/batch-1', [
      {
        key: 'goal-9/batch-1',
        before: { parent: 'goal-9' },
        after: { parent: 'goal-1' },
      },
    ]);
    expect(dropPlanText('goal-9/batch-1', unknown, TITLES)).toBeNull();
    expect(pushPlanText('goal-9/batch-1', unknown, TITLES)).toBeNull();
    expect(
      movePlanText(moveFactsFromPlan('goal-9/batch-1', 'goal-1', unknown), TITLES),
    ).toBeNull();
  });

  it('counts what sits below an item in the tree', () => {
    expect(descendants('goal-1/batch-1', sampleTree())).toEqual({
      subtask: 2,
      backlog: 1,
    });
    expect(descendants('goal-1/batch-2/subtask-1', sampleTree())).toEqual({});
  });
});
