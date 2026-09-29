import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import type { ItemView } from '../api/types.gen.ts';
import { ItemDetails } from './ItemDetails.tsx';

const HOSTILE =
  '<script>alert(1)</script><img src=x onerror=alert(2)>\n  **not markdown**';
const KEY = 'goal-1/batch-2/backlog-3';

function view(overrides: Partial<ItemView['item']> = {}): ItemView {
  return {
    item: {
      key: KEY,
      kind: 'backlog',
      title: '<b>bold?</b>',
      state: 'done',
      category: 'done',
      parent: 'goal-1/batch-2',
      version: 4,
      body: HOSTILE,
      awaiting_decision: null,
      found_on: 'goal-1/batch-2/subtask-1',
      covered_by: 'goal-1/batch-2/subtask-5',
      origin: null,
      aliases: ['goal-1/batch-1/backlog-1', 'goal-1/backlog-2'],
      created_at: '2026-09-28T00:00:00.000000Z',
      updated_at: '2026-09-28T00:00:00.000000Z',
      ...overrides,
    },
    children: { total: 0, by_category: {}, items: [], truncated: false },
    events: [
      {
        action: 'update',
        actor_kind: 'claude',
        client: 'chat',
        created_at: '2026-09-28T11:05:00.000000Z',
        redacted: false,
        changed: ['state'],
        before: { state: 'open' },
        after: { state: 'done' },
      },
      {
        action: 'create',
        actor_kind: 'claude',
        client: 'code',
        created_at: '2026-09-28T10:00:00.000000Z',
        redacted: false,
        changed: ['title'],
        before: null,
        after: { title: '<i>t</i>' },
      },
    ],
    decisions: [
      {
        key: 'goal-1/batch-2/decision-1',
        title: 'd',
        status: 'locked',
        owner: 'goal-1/batch-2',
        supersedes: null,
        version: 1,
        updated_at: 't',
        created_at: 't',
        body: '<script>alert(3)</script>',
      },
    ],
  };
}

const TITLES = new Map([['goal-1/batch-2/subtask-1', 'parse rows']]);

function renderDetails(item: ItemView, openBacklog?: number) {
  return render(
    <MemoryRouter initialEntries={['/x/tree']}>
      <ItemDetails prefix="x" view={item} titles={TITLES} openBacklog={openBacklog} />
    </MemoryRouter>,
  );
}

describe('ItemDetails', () => {
  it('renders stored text as literal text, never as HTML', () => {
    const { container } = renderDetails(view());
    expect(container.querySelector('script, img, b, i, u')).toBeNull();
    expect(screen.getByText('<b>bold?</b>')).toBeInTheDocument();
    expect(screen.getByText('<script>alert(3)</script>')).toBeInTheDocument();
  });

  it('keeps the body whitespace in a pre element, without markdown', () => {
    const { container } = renderDetails(view());
    const body = container.querySelector('pre.body');
    expect(body?.textContent).toBe(HOSTILE);
    expect(container.querySelector('strong, em')).toBeNull();
  });

  it('links found on and covered by, with nested keys in the query', () => {
    renderDetails(view());
    expect(
      screen.getByRole('link', { name: 'parse rows (goal-1/batch-2/subtask-1)' }),
    ).toHaveAttribute('href', '/x/tree?item=goal-1%2Fbatch-2%2Fsubtask-1');
    expect(
      screen.getByRole('link', { name: 'goal-1/batch-2/subtask-5' }),
    ).toHaveAttribute('href', '/x/tree?item=goal-1%2Fbatch-2%2Fsubtask-5');
    expect(screen.getByText('Found on')).toBeInTheDocument();
    expect(screen.getByText('Covered by')).toBeInTheDocument();
  });

  it('lists the old keys and the decisions made on the item', () => {
    renderDetails(view());
    expect(screen.getByText('goal-1/batch-1/backlog-1')).toHaveClass('key');
    expect(screen.getByText('goal-1/backlog-2')).toHaveClass('key');
    expect(screen.getByText('goal-1/batch-2/decision-1')).toBeInTheDocument();
  });

  it('shows history as "actor · client · date · change" lines', () => {
    renderDetails(view());
    const lines = [...document.querySelectorAll('.history li')].map(
      (li) => li.textContent,
    );
    expect(lines).toEqual([
      'claude · chat · 2026-09-28 11:05 · state: open → done',
      'claude · code · 2026-09-28 10:00 · created',
    ]);
  });

  it('shows the origin link on a subtask made from backlog', () => {
    renderDetails(
      view({ kind: 'subtask', origin: KEY, found_on: null, covered_by: null }),
    );
    expect(screen.getByText('Origin')).toBeInTheDocument();
    expect(screen.queryByText('Found on')).toBeNull();
  });

  it('shows the completion state of a blocked batch', () => {
    renderDetails(
      view({ kind: 'batch', key: 'goal-1/batch-2', category: 'open', state: 'open' }),
      2,
    );
    expect(
      screen.getByText('Blocked by 2 open backlog: all subtasks done.'),
    ).toHaveClass('warning');
    expect(
      screen.getByRole('button', { name: /Focus on this batch/ }),
    ).toBeInTheDocument();
  });

  it('says a goal completed automatically', () => {
    const goal = view({ kind: 'goal', key: 'goal-1', parent: null, found_on: null });
    goal.events = [
      { ...(goal.events[0] as ItemView['events'][number]), actor_kind: 'system' },
    ];
    renderDetails(goal);
    expect(
      screen.getByText('Completed automatically · 2026-09-28 11:05'),
    ).toBeInTheDocument();
    expect(screen.getByText('the project')).toBeInTheDocument();
  });
});
