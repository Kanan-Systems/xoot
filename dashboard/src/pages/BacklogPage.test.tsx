// The backlog tab's goal and batch filters (URL params, unknown values
// ignored), its collapse state under its own storage key, and the help on
// Cover and Push up.
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { storageKey } from '../lib/collapsed.ts';
import { mockApi, projectRoutes } from '../test/api.ts';
import { B1, B1_BACKLOG, G1, G1_BACKLOG, P_BACKLOG } from '../test/fixtures.ts';
import { renderApp } from '../test/renderApp.tsx';

const KEY = storageKey('x', 'backlog');

function rows(): string[] {
  return screen
    .queryAllByRole('button', { name: /^Cover / })
    .map((button) => (button.getAttribute('aria-label') ?? '').replace('Cover ', ''));
}

beforeEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
  mockApi(projectRoutes());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('backlog filters', () => {
  it('show only the chosen goal, then only the chosen batch, in the URL', async () => {
    renderApp('/x/backlog');
    await screen.findByRole('button', { name: `Cover ${P_BACKLOG}` });
    const filters = within(screen.getByRole('group', { name: 'Filter backlog' }));
    fireEvent.change(filters.getByRole('combobox', { name: 'Goal' }), {
      target: { value: G1 },
    });
    await waitFor(() => {
      expect(rows()).toEqual([G1_BACKLOG, B1_BACKLOG]);
    });
    fireEvent.change(filters.getByRole('combobox', { name: 'Batch' }), {
      target: { value: B1 },
    });
    await waitFor(() => {
      expect(rows()).toEqual([B1_BACKLOG]);
    });
    expect(screen.getByTestId('location')).toHaveTextContent(
      '/x/backlog?goal=goal-1&batch=goal-1%2Fbatch-1',
    );
  });

  it('ignore unknown values', async () => {
    renderApp('/x/backlog?goal=goal-99&batch=nope');
    await screen.findByRole('button', { name: `Cover ${P_BACKLOG}` });
    expect(rows()).toEqual([G1_BACKLOG, B1_BACKLOG, P_BACKLOG]);
    const filters = within(screen.getByRole('group', { name: 'Filter backlog' }));
    expect(filters.getByRole('combobox', { name: 'Goal' })).toHaveValue('');
  });
});

describe('backlog groups collapse', () => {
  it('under their own storage key, and start from it', async () => {
    renderApp('/x/backlog');
    const toggle = await screen.findByRole('button', { name: /goal-1\/batch-1 \(1\)/ });
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(rows()).toEqual([G1_BACKLOG, P_BACKLOG]);
    expect(localStorage.getItem(KEY)).toBe(JSON.stringify([B1]));
    expect(localStorage.getItem(storageKey('x'))).toBeNull();
  });

  it('read a stored set, and garbage as all expanded', async () => {
    localStorage.setItem(KEY, JSON.stringify(['@project']));
    const { unmount } = renderApp('/x/backlog');
    const project = await screen.findByRole('button', { name: /Project backlog/ });
    expect(project).toHaveAttribute('aria-expanded', 'false');
    unmount();
    localStorage.setItem(KEY, '{broken');
    renderApp('/x/backlog');
    await screen.findByRole('button', { name: `Cover ${P_BACKLOG}` });
    expect(rows()).toHaveLength(3);
  });
});

describe('backlog help', () => {
  it('explains Cover and Push up in plain words', async () => {
    renderApp('/x/backlog');
    const toggle = await screen.findByRole('button', {
      name: /About Cover and Push up/,
    });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(
      screen.getByText(/Turn a backlog item into a subtask in a batch you choose/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/from a batch to its goal, or from a goal to the/),
    ).toBeInTheDocument();
  });
});
