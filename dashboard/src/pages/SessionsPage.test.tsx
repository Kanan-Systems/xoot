import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi, projectRoutes } from '../test/api.ts';
import { renderApp } from '../test/renderApp.tsx';

describe('the sessions view', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    mockApi(projectRoutes());
  });

  it('hides closed sessions until asked, and shows the linked-item count', async () => {
    renderApp('/x/sessions');
    const table = await screen.findByRole('table', { name: 'Sessions' });
    expect(
      within(table).getByRole('link', { name: 'open one x-S2' }),
    ).toBeInTheDocument();
    expect(within(table).queryByRole('link', { name: /x-S1/ })).toBeNull();
    expect(within(table).getByText('2')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Show closed sessions' }));
    expect(
      await within(table).findByRole('link', { name: 'closed one x-S1' }),
    ).toBeInTheDocument();
  });

  it('a row click opens the detail, grouped by outcome, with captures', async () => {
    renderApp('/x/sessions?closed=1');
    fireEvent.click(await screen.findByRole('link', { name: 'closed one x-S1' }));
    const detail = await screen.findByRole('region', { name: 'Session x-S1' });
    await within(detail).findByText('wrapped up');
    const headings = within(detail)
      .getAllByRole('heading', { level: 4 })
      .map((heading) => heading.textContent);
    expect(headings).toEqual([
      'Done during it (1)',
      'Carried over (1)',
      "Parked in this session's backlog (1)",
    ]);
    const captured = within(detail).getByRole('table', {
      name: 'Captured in this session',
    });
    expect(
      within(captured).getByRole('link', { name: 'title of x-7 x-7' }),
    ).toBeInTheDocument();
    expect(within(detail).getByRole('link', { name: 'Show in tree' })).toHaveAttribute(
      'href',
      '/x/tree?session=x-S1&mode=highlight',
    );
  });

  it('an item in the detail opens the drawer over the sessions view', async () => {
    renderApp('/x/sessions?closed=1&session=x-S1');
    const detail = await screen.findByRole('region', { name: 'Session x-S1' });
    fireEvent.click(
      await within(detail).findByRole('link', { name: 'title of x-2 x-2' }),
    );
    await waitFor(() => {
      expect(screen.getByTestId('location').textContent).toBe(
        '/x/sessions?closed=1&session=x-S1&item=x-2',
      );
    });
    expect(
      await screen.findByRole('complementary', { name: 'Details of x-2' }),
    ).toBeInTheDocument();
  });
});
