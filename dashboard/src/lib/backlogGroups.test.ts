import { describe, expect, it } from 'vitest';

import type { BacklogView } from '../api/types.gen.ts';
import { backlogView } from '../test/api.ts';
import { B1, B1_BACKLOG, G1, G1_BACKLOG, P_BACKLOG } from '../test/fixtures.ts';
import {
  backlogBatches,
  backlogGoals,
  backlogTree,
  goalCount,
  validFilter,
} from './backlogGroups.ts';

const ALL = { goal: null, batch: null };

// One goal-level and one batch-level row more, under goal-10 and goal-2.
function wider(): BacklogView {
  const view = backlogView();
  const [, goalRow, batchRow] = view.items;
  if (goalRow === undefined || batchRow === undefined) {
    throw new Error('fixture rows');
  }
  view.items.push(
    { ...goalRow, key: 'goal-10/backlog-1', parent: 'goal-10' },
    { ...batchRow, key: 'goal-2/batch-3/backlog-1', parent: 'goal-2/batch-3' },
  );
  return view;
}

describe('backlogTree', () => {
  it('groups goal > batch, the goal backlog first, the project last', () => {
    const tree = backlogTree(backlogView(), ALL);
    expect(tree.goals).toEqual([
      {
        goal: G1,
        items: [expect.objectContaining({ key: G1_BACKLOG }) as unknown],
        batches: [
          {
            batch: B1,
            items: [expect.objectContaining({ key: B1_BACKLOG }) as unknown],
          },
        ],
      },
    ]);
    expect(tree.project.map((row) => row.key)).toEqual([P_BACKLOG]);
    expect(tree.goals.map(goalCount)).toEqual([2]);
  });

  it('sorts goals and batches by key, naturally', () => {
    const tree = backlogTree(wider(), ALL);
    expect(tree.goals.map((group) => group.goal)).toEqual([G1, 'goal-2', 'goal-10']);
    expect(tree.goals[1]?.batches.map((batch) => batch.batch)).toEqual([
      'goal-2/batch-3',
    ]);
  });

  it('shows only the goal, or only the batch, a filter names', () => {
    const byGoal = backlogTree(wider(), { goal: G1, batch: null });
    expect(byGoal.goals.map((group) => group.goal)).toEqual([G1]);
    expect(byGoal.project).toEqual([]);
    const byBatch = backlogTree(wider(), { goal: null, batch: B1 });
    expect(byBatch.goals).toEqual([
      {
        goal: G1,
        items: [],
        batches: [expect.objectContaining({ batch: B1 }) as unknown],
      },
    ]);
    expect(byBatch.project).toEqual([]);
  });
});

describe('backlog filters', () => {
  it('offer the goals and batches holding backlog', () => {
    expect(backlogGoals(wider())).toEqual([G1, 'goal-2', 'goal-10']);
    expect(backlogBatches(wider(), null)).toEqual([B1, 'goal-2/batch-3']);
    expect(backlogBatches(wider(), 'goal-2')).toEqual(['goal-2/batch-3']);
  });

  it('ignore values that name no group, or a batch of another goal', () => {
    expect(validFilter(wider(), 'goal-99', 'nope')).toEqual(ALL);
    expect(validFilter(wider(), G1, 'goal-2/batch-3')).toEqual({
      goal: G1,
      batch: null,
    });
    expect(validFilter(wider(), null, B1)).toEqual({ goal: null, batch: B1 });
  });
});
