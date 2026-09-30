import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { createQueryClient } from '../App.tsx';
import type { CoverOutput } from '../api/types.gen.ts';
import {
  backlogView,
  mockApi,
  projectRoutes,
  requests,
  sequence,
  writeError,
  type Routes,
} from '../test/api.ts';
import { B1, B1_BACKLOG, B2, G1_BACKLOG, item, P_BACKLOG } from '../test/fixtures.ts';
import { renderApp } from '../test/renderApp.tsx';
import { detail, pushed } from '../test/writes.ts';

afterEach(() => {
  vi.unstubAllGlobals();
});

const COVERS = 'POST /projects/x/backlog/covers';
const PUSHES = 'POST /projects/x/backlog/pushes';

function covered(subtask: string): CoverOutput {
  return {
    project: 'x',
    subtask: detail(subtask, { kind: 'subtask' }),
    backlog: item(B1_BACKLOG, 'backlog', B1, 'done'),
  };
}

function open(routes: Routes = {}) {
  const fetchMock = mockApi(projectRoutes(routes));
  renderApp('/x/backlog');
  return fetchMock;
}

async function coverForm(key: string) {
  fireEvent.click(await screen.findByRole('button', { name: `Cover ${key}` }));
  return screen.getByRole('form', { name: `Cover ${key}` });
}

function batchOptions(form: HTMLElement): (string | null)[] {
  return within(within(form).getByLabelText('Batch'))
    .getAllByRole('option')
    .map((option) => option.getAttribute('value'));
}

describe('covering backlog', () => {
  it('covers a batch-level item in its own batch without naming it', async () => {
    const fetchMock = open({ [COVERS]: covered('goal-1/batch-1/subtask-3') });
    const form = await coverForm(B1_BACKLOG);
    expect(within(form).getByLabelText('Batch')).toHaveValue(B1);
    expect(batchOptions(form)).toEqual([B1, B2]);
    fireEvent.click(within(form).getByRole('button', { name: 'Cover' }));
    expect(
      await screen.findByText(`Covered ${B1_BACKLOG} with goal-1/batch-1/subtask-3.`),
    ).toBeInTheDocument();
    expect(requests(fetchMock, 'POST').map((r) => r.body)).toEqual([
      { key: B1_BACKLOG },
    ]);
  });

  // The row leaves the list before the cover answer lands, as when a
  // refetch overtakes it: the notice must not depend on the row's form.
  it('keeps the notice when the covered row leaves the list first', async () => {
    const after = backlogView();
    after.items = after.items.filter((row) => row.key !== B1_BACKLOG);
    const fetchMock = mockApi(
      projectRoutes({
        [COVERS]: covered('goal-1/batch-1/subtask-3'),
        '/projects/x/backlog': sequence(backlogView(), after),
      }),
    );
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    vi.stubGlobal('fetch', (input: RequestInfo | URL, init?: RequestInit) =>
      init?.method === 'POST'
        ? gate.then(() => fetchMock(input, init))
        : fetchMock(input, init),
    );
    const client = createQueryClient();
    renderApp('/x/backlog', client);
    const form = await coverForm(B1_BACKLOG);
    fireEvent.click(within(form).getByRole('button', { name: 'Cover' }));
    await client.invalidateQueries({ queryKey: ['project', 'x', 'backlog'] });
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: `Cover ${B1_BACKLOG}` })).toBeNull();
    });
    release();
    expect(
      await screen.findByText(`Covered ${B1_BACKLOG} with goal-1/batch-1/subtask-3.`),
    ).toBeInTheDocument();
  });

  it('names another batch of the same goal', async () => {
    const fetchMock = open({ [COVERS]: covered('goal-1/batch-2/subtask-2') });
    const form = await coverForm(B1_BACKLOG);
    fireEvent.change(within(form).getByLabelText('Batch'), { target: { value: B2 } });
    fireEvent.click(within(form).getByRole('button', { name: 'Cover' }));
    await screen.findByText(/Covered/);
    expect(requests(fetchMock, 'POST').map((r) => r.body)).toEqual([
      { key: B1_BACKLOG, batch: B2 },
    ]);
  });

  it('requires a batch of the goal for a goal-level item', async () => {
    const fetchMock = open();
    const form = await coverForm(G1_BACKLOG);
    expect(batchOptions(form)).toEqual(['', B1, B2]);
    fireEvent.click(within(form).getByRole('button', { name: 'Cover' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Choose the batch');
    expect(requests(fetchMock, 'POST')).toHaveLength(0);
  });

  it('offers any batch for a project-level item', async () => {
    open();
    const form = await coverForm(P_BACKLOG);
    expect(batchOptions(form)).toEqual(['', B1, B2, 'goal-2/batch-1']);
  });

  it('shows a refused cover', async () => {
    open({
      [COVERS]: writeError(
        422,
        'BacklogError',
        'batch goal-2/batch-1 is not in goal goal-1',
      ),
    });
    const form = await coverForm(B1_BACKLOG);
    fireEvent.click(within(form).getByRole('button', { name: 'Cover' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('is not in goal goal-1');
  });
});

describe('pushing backlog', () => {
  it('previews in plain words first, then confirms with the token', async () => {
    const fetchMock = open({
      [PUSHES]: sequence(pushed('preview', 'tok-p'), pushed('applied', null)),
    });
    fireEvent.click(
      await screen.findByRole('button', { name: `Push ${G1_BACKLOG} up` }),
    );
    const region = await screen.findByRole('region', { name: /Confirm: Push/ });
    expect(within(region).getByText(/^Move backlog item/)).toHaveTextContent(
      "Move backlog item 'title of goal-1/backlog-1' up from goal 'title of goal-1' " +
        'to the project. It will be listed in the project backlog.',
    );
    // The raw field changes stay available under Details.
    const details = within(region).getByText('Details').closest('details');
    expect(details).toHaveTextContent(
      'goal-1/backlog-1: key goal-1/backlog-1 → backlog-3',
    );
    fireEvent.click(within(region).getByRole('button', { name: 'Confirm' }));
    expect(
      await screen.findByText(
        "Moved backlog item 'title of goal-1/backlog-1' up to the project. " +
          'It is now listed in the project backlog.',
      ),
    ).toBeInTheDocument();
    expect(requests(fetchMock, 'POST').map((r) => r.body)).toEqual([
      { key: G1_BACKLOG },
      { key: G1_BACKLOG, confirm_token: 'tok-p' },
    ]);
  });

  it('starts over when the token was already used', async () => {
    const fetchMock = open({
      [PUSHES]: sequence(
        pushed('preview', 'tok-1'),
        writeError(409, 'ConfirmTokenError', 'the confirm token has already been used'),
        pushed('preview', 'tok-2'),
      ),
    });
    fireEvent.click(
      await screen.findByRole('button', { name: `Push ${G1_BACKLOG} up` }),
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm' }));
    expect(await screen.findByText(/fresh one to review/)).toBeInTheDocument();
    expect(requests(fetchMock, 'POST').at(-1)?.body).toEqual({ key: G1_BACKLOG });
  });

  it('shows a refused push and offers none on project-level items', async () => {
    open({ [PUSHES]: writeError(422, 'BacklogError', 'already done or dropped') });
    fireEvent.click(
      await screen.findByRole('button', { name: `Push ${B1_BACKLOG} up` }),
    );
    expect(
      screen.getByRole('button', { name: `Cover ${P_BACKLOG}` }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: `Push ${P_BACKLOG} up` })).toBeNull();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'already done or dropped',
    );
  });
});
