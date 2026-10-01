import { describe, expect, it } from 'vitest';

import type { EventEntry, ItemDetail } from '../api/types.gen.ts';
import { itemView } from '../test/api.ts';
import { completionState, historyLine } from './history.ts';

function event(overrides: Partial<EventEntry>): EventEntry {
  return {
    action: 'update',
    actor_kind: 'claude',
    client: 'code',
    created_at: '2026-09-28T10:15:30.000000Z',
    redacted: false,
    changed: [],
    before: null,
    after: null,
    ...overrides,
  };
}

function detail(overrides: Partial<ItemDetail>): ItemDetail {
  return { ...itemView('goal-1/batch-1').item, ...overrides };
}

describe('historyLine', () => {
  it('is "actor · client · date · change"', () => {
    expect(historyLine(event({ action: 'create' }))).toBe(
      'claude · code · 2026-09-28 10:15 · created',
    );
    expect(
      historyLine(
        event({
          actor_kind: 'system',
          changed: ['state'],
          before: { state: 'open' },
          after: { state: 'done' },
        }),
      ),
    ).toBe('system · code · 2026-09-28 10:15 · state: open → done');
  });

  it('names a body change without its text, and marks redactions', () => {
    expect(historyLine(event({ changed: ['body'], redacted: true }))).toBe(
      'claude · code · 2026-09-28 10:15 · body changed (redacted)',
    );
    expect(
      historyLine(
        event({
          changed: ['parent'],
          before: { parent: 'goal-1' },
          after: { parent: null },
        }),
      ),
    ).toBe('claude · code · 2026-09-28 10:15 · moved from goal-1 to the project');
  });

  it('shows a move as origin and destination, never its key, parent or number', () => {
    const line = historyLine(
      event({
        changed: ['key', 'parent', 'number', 'state'],
        before: { key: 'goal-1/backlog-2', parent: 'goal-1', number: 2, state: 'open' },
        after: { key: 'backlog-1', parent: null, number: 1, state: 'open' },
      }),
      new Map([['goal-1', 'Alpha']]),
    );
    expect(line).toBe(
      'claude · code · 2026-09-28 10:15 · moved from Alpha to the project; state: open → open',
    );
    expect(line).not.toMatch(/key .* (->|→) .*; parent/);
    expect(line).not.toMatch(/(key|number):/);
  });
});

describe('completionState', () => {
  it('says what blocks a goal or batch', () => {
    expect(completionState(detail({}), [], 2)).toBe(
      'Blocked by 2 open backlog: all subtasks done.',
    );
  });

  it('says when the engine completed it', () => {
    const closed = event({
      actor_kind: 'system',
      changed: ['state'],
      before: { state: 'open' },
      after: { state: 'done' },
    });
    expect(
      completionState(detail({ category: 'done', state: 'done' }), [closed], undefined),
    ).toBe('Completed automatically · 2026-09-28 10:15');
  });

  it('explains the rule for an open one and says nothing for a subtask', () => {
    expect(completionState(detail({ kind: 'goal' }), [], undefined)).toMatch(
      /once all batches are done or dropped/,
    );
    expect(completionState(detail({ kind: 'subtask' }), [], undefined)).toBeNull();
  });
});
