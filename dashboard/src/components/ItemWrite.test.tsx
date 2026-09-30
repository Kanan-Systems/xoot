import { fireEvent, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  mockApi,
  projectRoutes,
  requests,
  sequence,
  writeError,
  type Routes,
} from '../test/api.ts';
import { B1, B2, G1, G2, S3 } from '../test/fixtures.ts';
import { renderApp } from '../test/renderApp.tsx';
import { CONFLICT_DETAILS, detail, previewed, updated } from '../test/writes.ts';

afterEach(() => {
  vi.unstubAllGlobals();
});

function open(key: string, routes: Routes = {}) {
  const fetchMock = mockApi(projectRoutes(routes));
  renderApp(`/x/backlog?item=${encodeURIComponent(key)}`);
  return fetchMock;
}

async function expand(label: string) {
  fireEvent.click(await screen.findByRole('button', { name: new RegExp(label) }));
}

const written = (key: string) => ({ project: 'x', item: detail(key) });

describe('create and capture in the drawer', () => {
  it('offers only the child kind the hierarchy allows', async () => {
    open(G1);
    expect(
      await screen.findByRole('button', { name: /Add batch/ }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Add subtask/ })).toBeNull();
  });

  it('offers no child on a subtask, but capture and move', async () => {
    open(S3);
    expect(await screen.findByRole('button', { name: /Capture/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Move to/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^.? ?Add / })).toBeNull();
  });

  it('adds a batch on the goal, focusing the title', async () => {
    const fetchMock = open(G1, { 'POST /projects/x/items': written('goal-1/batch-3') });
    await expand('Add batch');
    const form = screen.getByRole('form', { name: 'Add batch' });
    const title = within(form).getByLabelText('Title');
    expect(title).toHaveFocus();
    fireEvent.change(title, { target: { value: 'new batch' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Add batch' }));
    expect(await screen.findByText('Created goal-1/batch-3.')).toBeInTheDocument();
    expect(requests(fetchMock, 'POST').map((r) => r.body)).toEqual([
      { kind: 'batch', title: 'new batch', body: '', parent: G1 },
    ]);
  });

  it('shows a refused create', async () => {
    open(G1, {
      'POST /projects/x/items': writeError(
        422,
        'HierarchyError',
        'a batch needs a goal',
      ),
    });
    await expand('Add batch');
    const form = screen.getByRole('form', { name: 'Add batch' });
    fireEvent.change(within(form).getByLabelText('Title'), { target: { value: 't' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Add batch' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('a batch needs a goal');
  });

  it('requires a body saying why before capturing', async () => {
    const fetchMock = open(B2, {
      'POST /projects/x/backlog': written('goal-1/batch-2/backlog-2'),
    });
    await expand('Capture');
    const form = screen.getByRole('form', { name: 'Capture' });
    fireEvent.change(within(form).getByLabelText('Title'), {
      target: { value: 'gap' },
    });
    fireEvent.click(within(form).getByRole('button', { name: 'Capture' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('A body saying why');
    fireEvent.change(within(form).getByLabelText('Why it needs doing'), {
      target: { value: 'found it' },
    });
    fireEvent.click(within(form).getByRole('button', { name: 'Capture' }));
    expect(
      await screen.findByText('Captured goal-1/batch-2/backlog-2.'),
    ).toBeInTheDocument();
    expect(requests(fetchMock, 'POST').map((r) => r.body)).toEqual([
      { found_on: B2, title: 'gap', body: 'found it' },
    ]);
  });
});

describe('move in the drawer', () => {
  it('offers every goal but the current parent', async () => {
    open(B2);
    await expand('Move to');
    const form = screen.getByRole('form', { name: `Move ${B2}` });
    const values = within(form)
      .getAllByRole('option')
      .map((option) => option.getAttribute('value'));
    expect(values).toEqual(['', G2]);
  });

  it('moves a childless item at once with its version', async () => {
    const fetchMock = open(S3, { 'POST /projects/x/moves': updated(S3, 'reparent') });
    await expand('Move to');
    const form = screen.getByRole('form', { name: `Move ${S3}` });
    fireEvent.change(within(form).getByLabelText('New parent'), {
      target: { value: B1 },
    });
    fireEvent.click(within(form).getByRole('button', { name: 'Move' }));
    expect(await screen.findByText(`Moved ${S3} to ${B1}.`)).toBeInTheDocument();
    expect(requests(fetchMock, 'POST').map((r) => r.body)).toEqual([
      { key: S3, parent: B1, expected_version: 1 },
    ]);
  });

  it('confirms the plan of an item with children', async () => {
    const applied = {
      ...previewed('reparent'),
      phase: 'applied' as const,
      confirm_token: null,
    };
    const fetchMock = open(B2, {
      'POST /projects/x/moves': sequence(previewed('reparent', 'tok-3'), applied),
    });
    await expand('Move to');
    const form = screen.getByRole('form', { name: `Move ${B2}` });
    fireEvent.change(within(form).getByLabelText('New parent'), {
      target: { value: G2 },
    });
    fireEvent.click(within(form).getByRole('button', { name: 'Move' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm' }));
    expect(
      await screen.findByText(`Moved ${B2} to ${G2}: it is now goal-2/batch-2.`),
    ).toBeInTheDocument();
    expect(requests(fetchMock, 'POST').at(-1)?.body).toEqual({
      key: B2,
      parent: G2,
      expected_version: 1,
      confirm_token: 'tok-3',
    });
  });

  it('restarts with a fresh preview when the confirm token expired', async () => {
    const fetchMock = open(B2, {
      'POST /projects/x/moves': sequence(
        previewed('reparent', 'tok-1'),
        writeError(409, 'ConfirmTokenError', 'the confirm token has expired'),
        previewed('reparent', 'tok-2'),
      ),
    });
    await expand('Move to');
    const form = screen.getByRole('form', { name: `Move ${B2}` });
    fireEvent.change(within(form).getByLabelText('New parent'), {
      target: { value: G2 },
    });
    fireEvent.click(within(form).getByRole('button', { name: 'Move' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm' }));
    expect(await screen.findByText(/fresh one to review/)).toBeInTheDocument();
    expect(requests(fetchMock, 'POST')).toHaveLength(3);
  });

  it('shows a version conflict', async () => {
    open(S3, {
      'POST /projects/x/moves': writeError(
        409,
        'VersionConflictError',
        'stale',
        CONFLICT_DETAILS,
      ),
    });
    await expand('Move to');
    const form = screen.getByRole('form', { name: `Move ${S3}` });
    fireEvent.change(within(form).getByLabelText('New parent'), {
      target: { value: B1 },
    });
    fireEvent.click(within(form).getByRole('button', { name: 'Move' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Changed by: claude/code.',
    );
  });

  it('offers no move on a goal', async () => {
    open(G1);
    await screen.findByRole('button', { name: /Capture/ });
    expect(screen.queryByRole('button', { name: /Move to/ })).toBeNull();
  });
});

describe('recording a decision in the drawer', () => {
  it('records on the drawer item by default, superseding one of the same goal', async () => {
    const fetchMock = open(B2, {
      'POST /projects/x/decisions': {
        project: 'x',
        decision: {
          key: 'goal-1/batch-2/decision-1',
          owner: B2,
          title: 't',
          body: '',
          status: 'locked',
          supersedes: null,
          version: 1,
          created_at: 't',
          updated_at: 't',
        },
      },
    });
    await expand('Record decision');
    const form = screen.getByRole('form', { name: 'Record decision' });
    expect(within(form).getByLabelText('Made on')).toHaveValue(B2);
    const older = within(within(form).getByLabelText('Supersedes (optional)'))
      .getAllByRole('option')
      .map((option) => option.getAttribute('value'));
    // goal-1's superseded decision is not offered; goal-2's is another goal.
    expect(older).toEqual(['', 'goal-1/batch-1/decision-2']);
    fireEvent.change(within(form).getByLabelText('Title'), {
      target: { value: 'rule' },
    });
    fireEvent.change(within(form).getByLabelText('Status'), {
      target: { value: 'deferred' },
    });
    fireEvent.click(within(form).getByRole('button', { name: 'Record decision' }));
    expect(
      await screen.findByText('Recorded goal-1/batch-2/decision-1.'),
    ).toBeInTheDocument();
    expect(requests(fetchMock, 'POST').map((r) => r.body)).toEqual([
      { owner: B2, title: 'rule', body: '', status: 'deferred' },
    ]);
  });

  it('shows a refused decision', async () => {
    open(B2, {
      'POST /projects/x/decisions': writeError(422, 'DecisionError', 'not allowed'),
    });
    await expand('Record decision');
    const form = screen.getByRole('form', { name: 'Record decision' });
    fireEvent.change(within(form).getByLabelText('Title'), {
      target: { value: 'rule' },
    });
    fireEvent.click(within(form).getByRole('button', { name: 'Record decision' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('not allowed');
  });
});
