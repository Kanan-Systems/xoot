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
import { renderApp } from '../test/renderApp.tsx';

afterEach(() => {
  vi.unstubAllGlobals();
});

const PATCH = 'PATCH /projects/x';
const listed = (name: string) => ({
  projects: [{ key_prefix: 'x', name, aliases: [] }],
});

async function openForm(routes: Routes = {}) {
  const fetchMock = mockApi(projectRoutes(routes));
  renderApp('/x/backlog');
  await screen.findByRole('option', { name: 'Xproj (x)' });
  fireEvent.click(screen.getByRole('button', { name: /Rename/ }));
  return { fetchMock, form: screen.getByRole('form', { name: 'Rename project' }) };
}

describe('project rename', () => {
  it('sends the new name and reloads the project list', async () => {
    const { fetchMock, form } = await openForm({
      '/projects': sequence(listed('Xproj'), listed('Renamed')),
      [PATCH]: { key_prefix: 'x', name: 'Renamed', aliases: [] },
    });
    const name = within(form).getByLabelText('Name');
    expect(name).toHaveValue('Xproj');
    expect(name).toHaveFocus();
    fireEvent.change(name, { target: { value: 'Renamed' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('Project x is now "Renamed".')).toBeInTheDocument();
    expect(
      await screen.findByRole('option', { name: 'Renamed (x)' }),
    ).toBeInTheDocument();
    expect(requests(fetchMock, 'PATCH').map((r) => r.body)).toEqual([
      { name: 'Renamed' },
    ]);
    const reads = requests(fetchMock, 'GET').filter((r) => r.path === '/projects');
    expect(reads.length).toBeGreaterThanOrEqual(2);
  });

  it('adds an alias alone and shows a taken one', async () => {
    const { fetchMock, form } = await openForm({
      [PATCH]: writeError(
        409,
        'DuplicateError',
        "alias 'kr' is already used by another project",
        {
          alias: 'kr',
        },
      ),
    });
    fireEvent.change(within(form).getByLabelText('New alias (optional)'), {
      target: { value: 'kr' },
    });
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    expect(await within(form).findByRole('alert')).toHaveTextContent(
      "alias 'kr' is already used by another project",
    );
    expect(requests(fetchMock, 'PATCH').map((r) => r.body)).toEqual([{ alias: 'kr' }]);
  });

  it('refuses a malformed alias or no change before sending', async () => {
    const { fetchMock, form } = await openForm();
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    expect(await within(form).findByRole('alert')).toHaveTextContent(
      'Change the name or add an alias.',
    );
    fireEvent.change(within(form).getByLabelText('New alias (optional)'), {
      target: { value: 'Bad Alias' },
    });
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    expect(within(form).getByRole('alert')).toHaveTextContent(/An alias is/);
    expect(requests(fetchMock, 'PATCH')).toHaveLength(0);
  });

  it('shows a validation refusal', async () => {
    const { form } = await openForm({
      [PATCH]: writeError(422, 'ValidationError', 'invalid arguments: name'),
    });
    fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'N' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }));
    expect(await within(form).findByRole('alert')).toHaveTextContent(
      'invalid arguments',
    );
  });
});
