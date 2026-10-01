// The backlog tab: one staircase of headings like the Decisions tab (goal,
// then batch indented under it, then the project backlog), each group a
// list collapsible from its heading, each row with title, key, state,
// actions, then found on, why and created; a row click opens the drawer.
import { fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi, projectRoutes } from '../test/api.ts';
import { renderApp } from '../test/renderApp.tsx';

describe('backlog groups', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    mockApi(projectRoutes());
  });

  it('are grouped goal > batch, then the project backlog', async () => {
    renderApp('/x/backlog');
    const toggles = await screen.findAllByRole('button', { expanded: true });
    expect(toggles.map((toggle) => toggle.textContent)).toEqual([
      '▾ title of goal-1 goal-1 (2)',
      '▾ title of goal-1/batch-1 goal-1/batch-1 (1)',
      '▾ Project backlog (1)',
    ]);
    const tops = screen.getAllByRole('heading', { level: 2 });
    expect(tops.map((heading) => heading.textContent)).toEqual([
      '▾ title of goal-1 goal-1 (2)',
      '▾ Project backlog (1)',
    ]);
    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent(
      'goal-1/batch-1',
    );
  });

  it('show each row as title, key, state, actions, then its facts', async () => {
    renderApp('/x/backlog');
    const list = await screen.findByRole('list', { name: 'Project backlog' });
    // Rows under a heading, not a separate boxed table per group.
    expect(screen.queryByRole('table')).toBeNull();
    const row = within(list).getByRole('listitem');
    const head = row.firstElementChild as HTMLElement;
    expect([...head.children].map((part) => part.textContent)).toEqual([
      '⚑ title of backlog-1',
      'backlog-1',
      '○ open',
      'Cover',
    ]);
    const facts = within(row)
      .getAllByRole('term')
      .map((term) => [term.textContent, term.nextElementSibling?.textContent]);
    expect(facts).toEqual([
      ['Found on', '—'],
      ['Why', 'why backlog-1'],
      ['Created', '2026-09-28 09:30'],
    ]);
  });

  it('indent a batch under its goal as the Decisions tab does', async () => {
    renderApp('/x/backlog');
    const batch = await screen.findByRole('heading', { level: 3 });
    const section = batch.closest('section');
    expect(section).toHaveClass('backlog-group', 'depth-3');
    expect(section?.parentElement?.closest('section')).toHaveClass(
      'backlog-group',
      'depth-2',
    );
  });

  it('hide and show the rows, toggling aria-expanded', async () => {
    renderApp('/x/backlog');
    const toggle = await screen.findByRole('button', { name: /Project backlog/ });
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('list', { name: 'Project backlog' })).toBeNull();
    expect(screen.getByRole('list', { name: 'title of goal-1' })).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('title of backlog-1')).toBeInTheDocument();
  });
});
