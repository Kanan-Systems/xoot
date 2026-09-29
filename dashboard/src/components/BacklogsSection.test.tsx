// kanan-87: every backlog group collapses and expands from its heading.
import { fireEvent, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi, projectRoutes } from '../test/api.ts';
import { renderApp } from '../test/renderApp.tsx';

describe('backlog groups', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    mockApi(projectRoutes());
  });

  it('start expanded, with the title, key and item count on the toggle', async () => {
    renderApp('/x/backlog');
    const toggles = await screen.findAllByRole('button', { expanded: true });
    expect(toggles.map((toggle) => toggle.textContent)).toEqual([
      '▾ open one x-S2 (1)',
      '▾ Project backlog (1)',
      '▾ Unfiled (2)',
    ]);
  });

  it('hides and shows the rows, toggling aria-expanded', async () => {
    renderApp('/x/backlog');
    const toggle = await screen.findByRole('button', { name: /Project backlog/ });
    expect(screen.getByRole('table', { name: 'Project backlog' })).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('table', { name: 'Project backlog' })).toBeNull();
    expect(screen.queryByText('title of x-10')).toBeNull();
    expect(screen.getByRole('table', { name: 'Unfiled' })).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('title of x-10')).toBeInTheDocument();
  });
});
