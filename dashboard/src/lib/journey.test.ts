import { describe, expect, it } from 'vitest';

import type { SubtreeOutput } from '../api/types.gen.ts';
import { dropJourney, moveJourney, pushJourney, type Journey } from './journey.ts';

const TITLES = new Map([
  ['goal-1', 'Alpha'],
  ['goal-2', 'Beta'],
  ['goal-1/batch-1', 'Writer'],
  ['goal-1/batch-2', 'Reader'],
  ['goal-2/batch-1', 'Parser'],
  ['goal-1/batch-1/subtask-1', 'Write rows'],
  ['goal-1/batch-1/backlog-3', 'Finding 3'],
  ['goal-1/backlog-2', 'Finding 2'],
]);

// The staircase as indented lines, the destination under an arrow.
function lines({ from, to }: Journey): string[] {
  const line = (depth: number, text: string, note: string | null) =>
    `${'  '.repeat(depth)}${text}${note === null ? '' : ` (${note})`}`;
  return [
    ...from.map((step) => line(step.depth, step.text, step.note)),
    ...(to.length === 0 ? [] : ['->']),
    ...to.map((step) => line(step.depth + 2, step.text, step.note)),
  ];
}

function pushPlan(key: string, parent: string | null): SubtreeOutput {
  return {
    root: key,
    changes: [
      { key, before: { key, parent: 'x', number: 3 }, after: { key: 'y', parent } },
    ],
  };
}

const RAW = /key .* (->|→) .*; parent/;

describe('origin and destination', () => {
  it('pushes a batch backlog item up to its goal', () => {
    const journey = pushJourney(
      'goal-1/batch-1/backlog-3',
      pushPlan('goal-1/batch-1/backlog-3', 'goal-1'),
      TITLES,
    );
    expect(lines(journey)).toEqual([
      'Alpha',
      '  Writer',
      '    Finding 3 (backlog item)',
      '->',
      '    Alpha',
      '      (goal backlog)',
    ]);
  });

  it('pushes a goal backlog item up to the project', () => {
    const journey = pushJourney(
      'goal-1/backlog-2',
      pushPlan('goal-1/backlog-2', null),
      TITLES,
    );
    expect(lines(journey)).toEqual([
      'Alpha',
      '  Finding 2 (backlog item)',
      '->',
      '    (project backlog)',
    ]);
  });

  it('moves a subtask between batches and a batch between goals', () => {
    expect(
      lines(moveJourney('goal-1/batch-1/subtask-1', 'goal-2/batch-1', TITLES)),
    ).toEqual([
      'Alpha',
      '  Writer',
      '    Write rows (subtask)',
      '->',
      '    Beta',
      '      Parser',
      '        Write rows (subtask)',
    ]);
    expect(lines(moveJourney('goal-1/batch-2', 'goal-2', TITLES))).toEqual([
      'Alpha',
      '  Reader (batch)',
      '->',
      '    Beta',
      '      Reader (batch)',
    ]);
  });

  it('drops an item with the open items that drop with it, indented', () => {
    const plan: SubtreeOutput = {
      root: 'goal-1/batch-1',
      changes: [
        'goal-1/batch-1/subtask-10',
        'goal-1/batch-1',
        'goal-1/batch-1/backlog-3',
        'goal-1/batch-1/subtask-1',
      ].map((key) => ({ key, before: { state: 'open' }, after: { state: 'dropped' } })),
    };
    expect(lines(dropJourney('goal-1/batch-1', plan, TITLES))).toEqual([
      'Writer (batch)',
      '  Finding 3 (backlog item)',
      '  Write rows (subtask)',
      '  goal-1/batch-1/subtask-10 (subtask)',
    ]);
  });

  it('falls back to the key, only in its place, when a title is unknown', () => {
    expect(lines(moveJourney('goal-9/batch-1', 'goal-2', TITLES))).toEqual([
      'goal-9',
      '  goal-9/batch-1 (batch)',
      '->',
      '    Beta',
      '      goal-9/batch-1 (batch)',
    ]);
  });

  it('never words a change as raw key, parent or number fields', () => {
    const all = [
      pushJourney('goal-1/backlog-2', pushPlan('goal-1/backlog-2', null), TITLES),
      moveJourney('goal-1/batch-2', 'goal-2', TITLES),
      dropJourney('goal-1/batch-1', pushPlan('goal-1/batch-1', null), TITLES),
    ];
    for (const journey of all) {
      expect(lines(journey).join('; ')).not.toMatch(RAW);
    }
  });
});
