// A project typed by alias in the URL redirects to the prefix URL, keeping
// the view and the query; a name no project has says so and reads nothing
// of that project.
import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi, projectRoutes, requests } from '../test/api.ts';
import { B1 } from '../test/fixtures.ts';
import { mockReactFlowDom } from '../test/reactFlow.ts';
import { renderApp } from '../test/renderApp.tsx';

const PROJECTS = {
  '/projects': { projects: [{ key_prefix: 'x', name: 'xoot', aliases: ['xoot'] }] },
};

function location(): string {
  return screen.getByTestId('location').textContent;
}

describe('the project segment', () => {
  let fetchMock: ReturnType<typeof mockApi>;

  beforeEach(() => {
    vi.unstubAllGlobals();
    mockReactFlowDom();
    fetchMock = mockApi(projectRoutes(PROJECTS));
  });

  it('an alias redirects to the prefix URL', async () => {
    renderApp('/xoot');
    await waitFor(() => {
      expect(location()).toBe('/x/tree');
    });
    expect(
      await screen.findByRole('region', { name: 'Item tree' }),
    ).toBeInTheDocument();
  });

  it('an alias keeps the view and the query', async () => {
    const search = `?item=${encodeURIComponent(B1)}`;
    renderApp(`/xoot/backlog${search}`);
    await waitFor(() => {
      expect(location()).toBe(`/x/backlog${search}`);
    });
  });

  it('a prefix opens without a redirect', async () => {
    renderApp('/x/decisions');
    expect(
      await screen.findByRole('navigation', { name: 'Views' }),
    ).toBeInTheDocument();
    expect(location()).toBe('/x/decisions');
  });

  it('an unknown name says no project has it', async () => {
    renderApp('/nope/tree');
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No project named “nope”.',
    );
    expect(location()).toBe('/nope/tree');
    expect(requests(fetchMock).map((sent) => sent.path)).toEqual(['/projects']);
  });
});
