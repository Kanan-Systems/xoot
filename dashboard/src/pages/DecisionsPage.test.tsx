// The decisions tab: grouped by goal, each decision with its owner's level
// and title, supersede links both ways, goal and level filters, and bodies
// that expand as plain text.
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { DecisionView } from '../api/types.gen.ts';
import { mockApi, projectRoutes } from '../test/api.ts';
import { renderApp } from '../test/renderApp.tsx';

const OLD = 'goal-1/decision-1';
const NEW = 'goal-1/batch-1/decision-2';
const LATER = 'goal-2/batch-1/subtask-1/decision-1';
const BODY = '<script>alert(1)</script>\n  kept as text';

function decisionView(): DecisionView {
  return {
    decision: {
      key: OLD,
      title: 'old rule',
      status: 'superseded',
      owner: 'goal-1',
      supersedes: null,
      version: 1,
      updated_at: 't',
      created_at: 't',
      body: BODY,
    },
  };
}

function row(key: string): HTMLElement {
  const element = document.getElementById(`decision-${key}`);
  if (element === null) {
    throw new Error(`no row ${key}`);
  }
  return element;
}

function shown(): string[] {
  return [...document.querySelectorAll('.decision-row')].map((li) =>
    li.id.replace(/^decision-/, ''),
  );
}

describe('the decisions view', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    mockApi(projectRoutes({ [`/projects/x/decisions/${OLD}`]: decisionView() }));
  });

  it('groups by goal, headed by the goal title with its key', async () => {
    renderApp('/x/decisions');
    await screen.findByRole('button', { name: /new rule/ });
    const headings = screen.getAllByRole('heading', { level: 2 });
    expect(headings.map((heading) => heading.textContent)).toEqual([
      'title of goal-1 goal-1 (2)',
      'title of goal-2 goal-2 (1)',
    ]);
    expect(shown()).toEqual([NEW, OLD, LATER]);
  });

  it("shows each owner's level and title, linked to its drawer", async () => {
    renderApp('/x/decisions');
    await screen.findByRole('button', { name: /new rule/ });
    const newer = within(row(NEW));
    expect(newer.getByText(/^Batch:/)).toBeInTheDocument();
    expect(
      newer.getByRole('link', { name: 'title of goal-1/batch-1 (goal-1/batch-1)' }),
    ).toHaveAttribute('href', '/x/decisions?item=goal-1%2Fbatch-1');
    expect(within(row(OLD)).getByText(/^Goal:/)).toBeInTheDocument();
    expect(within(row(LATER)).getByText(/^Subtask:/)).toBeInTheDocument();
  });

  it('links supersedes both ways, with a status chip', async () => {
    renderApp('/x/decisions');
    await screen.findByRole('button', { name: /new rule/ });
    const newer = within(row(NEW));
    expect(newer.getByRole('link', { name: `old rule (${OLD})` })).toHaveAttribute(
      'href',
      `#decision-${OLD}`,
    );
    expect(newer.getByText('Locked')).toHaveClass('chip');
    const older = within(row(OLD));
    expect(older.getByText(/Superseded by/)).toBeInTheDocument();
    expect(older.getByRole('link', { name: `new rule (${NEW})` })).toHaveAttribute(
      'href',
      `#decision-${NEW}`,
    );
  });

  it('filters by goal and by level, in the URL', async () => {
    renderApp('/x/decisions');
    await screen.findByRole('button', { name: /new rule/ });
    const filters = within(screen.getByRole('group', { name: 'Filter decisions' }));
    fireEvent.change(filters.getByRole('combobox', { name: 'Goal' }), {
      target: { value: 'goal-1' },
    });
    await waitFor(() => {
      expect(shown()).toEqual([NEW, OLD]);
    });
    fireEvent.change(filters.getByRole('combobox', { name: 'Level' }), {
      target: { value: 'goal' },
    });
    await waitFor(() => {
      expect(shown()).toEqual([OLD]);
    });
    expect(screen.getByTestId('location')).toHaveTextContent(
      '/x/decisions?goal=goal-1&level=goal',
    );
  });

  it('expands a body inline as plain text', async () => {
    renderApp('/x/decisions');
    const toggle = await screen.findByRole('button', { name: /old rule/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const body = await within(row(OLD)).findByText(/kept as text/);
    expect(body.tagName).toBe('PRE');
    expect(body.textContent).toBe(BODY);
    expect(document.querySelector('.decision-list script')).toBeNull();
  });
});
