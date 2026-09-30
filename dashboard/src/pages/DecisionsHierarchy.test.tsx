// The decisions hierarchy's collapse state and the inline decision editor.
import { fireEvent, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { DecisionView } from '../api/types.gen.ts';
import { storageKey } from '../lib/collapsed.ts';
import {
  decisionsView,
  mockApi,
  projectRoutes,
  requests,
  writeError,
  type Routes,
} from '../test/api.ts';
import { renderApp } from '../test/renderApp.tsx';
import { CONFLICT_DETAILS } from '../test/writes.ts';

const OLD = 'goal-1/decision-1';
const KEY = storageKey('x', 'decisions');

function detailOf(key: string): DecisionView {
  const summary = decisionsView().decisions.find((d) => d.key === key);
  if (summary === undefined) {
    throw new Error(key);
  }
  return { decision: { ...summary, body: 'the body', created_at: 't' } };
}

function open(routes: Routes = {}) {
  const fetchMock = mockApi(
    projectRoutes({ [`/projects/x/decisions/${OLD}`]: detailOf(OLD), ...routes }),
  );
  renderApp('/x/decisions');
  return fetchMock;
}

function shown(): string[] {
  return [...document.querySelectorAll('.decision-row')].map((li) =>
    li.id.replace(/^decision-/, ''),
  );
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('decision groups collapse', () => {
  it('per heading, remembered under their own storage key', async () => {
    open();
    const toggle = await screen.findByRole('button', { name: /goal-1\/batch-1 \(1\)/ });
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(shown()).toEqual([OLD, 'goal-2/batch-1/subtask-1/decision-1']);
    expect(localStorage.getItem(KEY)).toBe('["goal-1/batch-1"]');
    expect(localStorage.getItem(storageKey('x'))).toBeNull();
  });

  it('start from the stored set and read garbage as all expanded', async () => {
    localStorage.setItem(KEY, '["goal-2"]');
    open();
    const goal2 = await screen.findByRole('button', { name: /goal-2 \(1\)/ });
    expect(goal2).toHaveAttribute('aria-expanded', 'false');
    expect(shown()).toEqual([OLD, 'goal-1/batch-1/decision-2']);
  });

  it('tolerate garbage in storage', async () => {
    localStorage.setItem(KEY, '{broken');
    open();
    await screen.findByRole('button', { name: /goal-2 \(1\)/ });
    expect(screen.getAllByRole('button', { expanded: true }).length).toBeGreaterThan(0);
    expect(shown()).toHaveLength(3);
  });

  it('still toggle when storage refuses writes', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota');
    });
    open();
    const toggle = await screen.findByRole('button', { name: /goal-2 \(1\)/ });
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });

  it('put decisions whose owner is gone in the last group', async () => {
    const view = decisionsView();
    const [first] = view.decisions;
    if (first !== undefined) {
      view.decisions.push({ ...first, key: 'goal-9/decision-1', owner: null });
    }
    open({ '/projects/x/decisions': view });
    await screen.findByRole('button', { name: /Owner gone/ });
    const headings = screen.getAllByRole('heading', { level: 2 });
    expect(headings.at(-1)).toHaveTextContent('Owner gone (1)');
  });
});

describe('editing a decision in place', () => {
  async function editForm() {
    fireEvent.click(await screen.findByRole('button', { name: `Edit ${OLD}` }));
    return screen.findByRole('form', { name: `Edit ${OLD}` });
  }

  it('sends the changed fields with the version it started from', async () => {
    const fetchMock = open({
      [`PATCH /projects/x/decisions/${OLD}`]: detailOf(OLD),
    });
    const form = await editForm();
    expect(within(form).getByLabelText('Title')).toHaveFocus();
    expect(within(form).getByLabelText('Body')).toHaveValue('the body');
    fireEvent.change(within(form).getByLabelText('Body'), { target: { value: 'new' } });
    // Status is a radio group, not a select; a superseded decision keeps its
    // own status as a third choice so an edit does not change it silently.
    const status = within(form).getByRole('group', { name: 'Status' });
    expect(
      within(status)
        .getAllByRole('radio')
        .map((r) => r.getAttribute('value')),
    ).toEqual(['superseded', 'locked', 'deferred']);
    expect(within(status).getByRole('radio', { name: 'Superseded' })).toBeChecked();
    expect(within(form).queryByRole('combobox', { name: 'Status' })).toBeNull();
    fireEvent.click(within(status).getByRole('radio', { name: 'Deferred' }));
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    expect(await screen.findByText(`Saved ${OLD}.`)).toBeInTheDocument();
    expect(requests(fetchMock, 'PATCH').map((r) => r.body)).toEqual([
      { expected_version: 1, body: 'new', status: 'deferred' },
    ]);
  });

  it('shows a version conflict with fields and actors', async () => {
    open({
      [`PATCH /projects/x/decisions/${OLD}`]: writeError(
        409,
        'VersionConflictError',
        'stale',
        CONFLICT_DETAILS,
      ),
    });
    const form = await editForm();
    fireEvent.change(within(form).getByLabelText('Title'), { target: { value: 't2' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    const alert = await within(form).findByRole('alert');
    expect(alert).toHaveTextContent('Changed meanwhile: title, state.');
    expect(alert).toHaveTextContent('Changed by: claude/code.');
  });

  it('shows a validation refusal', async () => {
    open({
      [`PATCH /projects/x/decisions/${OLD}`]: writeError(
        422,
        'DecisionError',
        'refused',
      ),
    });
    const form = await editForm();
    fireEvent.change(within(form).getByLabelText('Title'), { target: { value: 't2' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    expect(await within(form).findByRole('alert')).toHaveTextContent('refused');
  });
});
