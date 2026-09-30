// The backlog tab: tables grouped goal > batch, then the project backlog,
// each group collapsible from its heading, with the title, key, state,
// found on, why, created and actions columns; a row click opens the drawer.
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

  it('have the seven columns, with "why" as the first line of the body', async () => {
    renderApp('/x/backlog');
    const table = await screen.findByRole('table', { name: 'Project backlog' });
    const headers = within(table).getAllByRole('columnheader');
    expect(headers.map((header) => header.textContent)).toEqual([
      'Title',
      'Key',
      'State',
      'Found on',
      'Why',
      'Created',
      'Actions',
    ]);
    const [, row] = within(table).getAllByRole('row');
    const cells = within(row as HTMLElement).getAllByRole('cell');
    expect(cells.map((cell) => cell.textContent)).toEqual([
      '⚑ title of backlog-1',
      'backlog-1',
      '○ open',
      '—',
      'why backlog-1',
      '2026-09-28 09:30',
      'Cover',
    ]);
  });

  it('hide and show the rows, toggling aria-expanded', async () => {
    renderApp('/x/backlog');
    const toggle = await screen.findByRole('button', { name: /Project backlog/ });
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('table', { name: 'Project backlog' })).toBeNull();
    expect(screen.getByRole('table', { name: 'title of goal-1' })).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('title of backlog-1')).toBeInTheDocument();
  });
});
