import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import type { ItemView } from '../api/types.gen.ts';
import { ItemDetails } from './DetailPanel.tsx';

const HOSTILE =
  '<script>alert(1)</script><img src=x onerror=alert(2)>\n  **not markdown**';

function view(): ItemView {
  return {
    item: {
      key: 'x-1',
      kind: 'goal',
      title: '<b>bold?</b>',
      state: 'active',
      category: 'active',
      parent: null,
      backlog_session: null,
      version: 4,
      body: HOSTILE,
      awaiting_decision: null,
      unfiled: false,
      created_at: '2026-09-28T00:00:00.000000Z',
      updated_at: '2026-09-28T00:00:00.000000Z',
    },
    children: { total: 0, by_category: {}, items: [], truncated: false },
    events: [
      {
        action: 'create',
        actor_kind: 'claude',
        client: 'code',
        session: 'x-S1',
        created_at: '2026-09-28T00:00:00.000000Z',
        redacted: false,
        changed: ['title'],
        before: null,
        after: { title: '<i>t</i>' },
      },
    ],
    sessions: [
      {
        key: 'x-S1',
        title: '<u>session</u>',
        client: 'code',
        status: 'open',
        started_at: 't',
        closed_at: null,
      },
    ],
    decisions: [
      {
        key: 'x-D1',
        title: 'd',
        status: 'locked',
        scope: 'x-1',
        supersedes: null,
        version: 1,
        updated_at: 't',
        created_at: 't',
        body: '<script>alert(3)</script>',
      },
    ],
  };
}

describe('ItemDetails', () => {
  it('renders stored text as literal text, never as HTML', () => {
    const { container } = render(
      <MemoryRouter>
        <ItemDetails prefix="x" view={view()} />
      </MemoryRouter>,
    );
    expect(container.querySelector('script, img, b, i, u')).toBeNull();
    expect(screen.getByText('<b>bold?</b>')).toBeInTheDocument();
    expect(screen.getByText('<script>alert(3)</script>')).toBeInTheDocument();
    expect(screen.getByText(/<u>session<\/u>/)).toBeInTheDocument();
  });

  it('keeps the body whitespace in a pre element, without markdown', () => {
    const { container } = render(
      <MemoryRouter>
        <ItemDetails prefix="x" view={view()} />
      </MemoryRouter>,
    );
    const body = container.querySelector('pre.body');
    expect(body?.textContent).toBe(HOSTILE);
    expect(container.querySelector('strong, em')).toBeNull();
  });

  it('shows state, version, parent, sessions, decisions and history', () => {
    render(
      <MemoryRouter>
        <ItemDetails prefix="x" view={view()} />
      </MemoryRouter>,
    );
    expect(screen.getByText('active (Active)', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('none')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Focus on this goal/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '<u>session</u> (x-S1)' })).toHaveAttribute(
      'href',
      '/x/sessions?session=x-S1',
    );
    expect(
      screen.getByText(/create by claude\/code in x-S1: title/),
    ).toBeInTheDocument();
  });
});
