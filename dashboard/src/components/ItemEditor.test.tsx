import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { createQueryClient } from '../App.tsx';
import {
  itemView,
  mockApi,
  projectRoutes,
  requests,
  sequence,
  writeError,
  type Routes,
} from '../test/api.ts';
import { B2, S3 } from '../test/fixtures.ts';
import { renderApp } from '../test/renderApp.tsx';
import { CONFLICT_DETAILS, previewed, updated } from '../test/writes.ts';

afterEach(() => {
  vi.unstubAllGlobals();
});

const PATCH_B2 = `PATCH /projects/x/items/${B2}`;

function open(routes: Routes, key = B2) {
  const fetchMock = mockApi(projectRoutes(routes));
  const client = createQueryClient();
  renderApp(`/x/backlog?item=${encodeURIComponent(key)}`, client);
  return { fetchMock, client };
}

// Edits once the workflow is in, so the state picker offers every state.
async function startEditing() {
  fireEvent.click(await screen.findByRole('button', { name: 'Edit' }));
  const form = screen.getByRole('form', { name: /^Edit / });
  await waitFor(() => {
    expect(within(form).getAllByRole('option').length).toBeGreaterThan(1);
  });
  return form;
}

describe('drawer editing', () => {
  it('focuses the title and saves only the changed fields with the version', async () => {
    const { fetchMock } = open({ [PATCH_B2]: updated(B2, 'update') });
    const form = await startEditing();
    const title = within(form).getByLabelText('Title');
    expect(title).toHaveFocus();
    fireEvent.change(title, { target: { value: 'renamed' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    expect(await screen.findByText(`Saved ${B2}.`)).toBeInTheDocument();
    expect(requests(fetchMock, 'PATCH').map((r) => r.body)).toEqual([
      { expected_version: 1, title: 'renamed' },
    ]);
    expect(screen.queryByRole('form', { name: /^Edit / })).toBeNull();
  });

  it('keeps the draft through a refetch and warns that the version moved', async () => {
    const newer = itemView(B2);
    newer.item.version = 2;
    newer.item.title = 'changed by claude';
    const item = sequence(itemView(B2), newer);
    const { client } = open({ [`/projects/x/items/${B2}`]: item });
    const form = await startEditing();
    const title = within(form).getByLabelText('Title');
    fireEvent.change(title, { target: { value: 'my draft' } });
    await client.invalidateQueries({ queryKey: ['project', 'x'] });
    expect(
      await screen.findByText(/changed while you were editing/),
    ).toBeInTheDocument();
    expect(title).toHaveValue('my draft');
  });

  it('shows a version conflict with its fields and actors, without retrying', async () => {
    const { fetchMock } = open({
      [PATCH_B2]: writeError(409, 'VersionConflictError', 'stale', CONFLICT_DETAILS),
    });
    const form = await startEditing();
    fireEvent.change(within(form).getByLabelText('Title'), { target: { value: 'x' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Changed meanwhile: title, state.');
    expect(alert).toHaveTextContent('Changed by: claude/code.');
    expect(requests(fetchMock, 'PATCH')).toHaveLength(1);
  });

  it('lists the open children that refuse a done', async () => {
    open({
      [PATCH_B2]: writeError(422, 'OpenChildrenError', 'open children remain', {
        key: B2,
        open_keys: [S3],
      }),
    });
    const form = await startEditing();
    fireEvent.change(within(form).getByLabelText('State'), {
      target: { value: 'done' },
    });
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('open children remain');
    expect(within(alert).getByText(S3)).toBeInTheDocument();
  });

  it('confirms a drop of an item with children, then sends the token', async () => {
    const parent = itemView(B2);
    parent.children.total = 1;
    const { fetchMock } = open({
      [`/projects/x/items/${B2}`]: parent,
      [PATCH_B2]: sequence(previewed('drop', 'tok-9'), updated(B2, 'drop')),
    });
    const form = await startEditing();
    fireEvent.change(within(form).getByLabelText('State'), {
      target: { value: 'dropped' },
    });
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm' }));
    expect(
      await screen.findByText(`Dropped ${B2} with its children.`),
    ).toBeInTheDocument();
    expect(requests(fetchMock, 'PATCH').map((r) => r.body)).toEqual([
      { expected_version: 1, state: 'dropped' },
      { expected_version: 1, state: 'dropped', confirm_token: 'tok-9' },
    ]);
  });

  it('words the drop of an item with children plainly, before and after', async () => {
    const parent = itemView(B2);
    parent.children.total = 1;
    const changes = [
      { key: S3, before: { state: 'open' }, after: { state: 'dropped' } },
      { key: B2, before: { state: 'open' }, after: { state: 'dropped' } },
    ];
    const preview = previewed('drop', 'tok-5', changes);
    const applied = { ...preview, phase: 'applied' as const, confirm_token: null };
    open({
      [`/projects/x/items/${B2}`]: parent,
      [PATCH_B2]: sequence(preview, applied),
    });
    const form = await startEditing();
    fireEvent.change(within(form).getByLabelText('State'), {
      target: { value: 'dropped' },
    });
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    const region = await screen.findByRole('region', { name: /Confirm: Save/ });
    expect(region).toHaveTextContent(
      `Drop batch 'title of ${B2}' and its 1 open subtask.`,
    );
    const dropped = within(region).getByRole('list', { name: 'Dropped' });
    expect(
      within(dropped)
        .getAllByRole('listitem')
        .map((line) => [line.className, line.textContent]),
    ).toEqual([
      ['stair-0', `title of ${B2} (batch)`],
      ['stair-1', `title of ${S3} (subtask)`],
    ]);
    expect(region.textContent).not.toMatch(/key .* (->|→) .*; parent/);
    fireEvent.click(within(region).getByRole('button', { name: 'Confirm' }));
    expect(
      await screen.findByText(`Dropped batch 'title of ${B2}' and its 1 open subtask.`),
    ).toBeInTheDocument();
  });

  it('refuses a drop with children combined with other fields before sending', async () => {
    const parent = itemView(B2);
    parent.children.total = 1;
    const { fetchMock } = open({ [`/projects/x/items/${B2}`]: parent });
    const form = await startEditing();
    fireEvent.change(within(form).getByLabelText('State'), {
      target: { value: 'dropped' },
    });
    fireEvent.change(within(form).getByLabelText('Title'), { target: { value: 'x' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/saved on its own/);
    expect(requests(fetchMock, 'PATCH')).toHaveLength(0);
  });

  it('refuses an empty title before sending', async () => {
    const { fetchMock } = open({});
    const form = await startEditing();
    fireEvent.change(within(form).getByLabelText('Title'), { target: { value: '  ' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('A title is required.');
    expect(requests(fetchMock, 'PATCH')).toHaveLength(0);
  });

  it('offers every state of an unrestricted kind', async () => {
    open({});
    const form = await startEditing();
    const states = within(within(form).getByLabelText('State')).getAllByRole('option');
    expect(states.map((option) => option.getAttribute('value'))).toEqual([
      'open',
      'active',
      'blocked',
      'done',
      'dropped',
    ]);
  });

  it('offers the current state and its allowed moves on a restricted kind', async () => {
    open({}, S3);
    const form = await startEditing();
    const states = within(form).getAllByRole('option');
    expect(states.map((option) => option.getAttribute('value'))).toEqual([
      'open',
      'active',
      'dropped',
    ]);
  });

  it('keeps the drawer open on Escape inside a field, closes on Cancel', async () => {
    open({});
    const form = await startEditing();
    fireEvent.keyDown(within(form).getByLabelText('Title'), { key: 'Escape' });
    expect(screen.getByRole('complementary')).toBeInTheDocument();
    fireEvent.click(within(form).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('form', { name: /^Edit / })).toBeNull();
    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
  });
});
