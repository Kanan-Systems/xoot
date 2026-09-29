// kanan-89: each tab's "What is this?" help, collapsed by default.
import { fireEvent, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi, projectRoutes } from '../test/api.ts';
import { mockReactFlowDom } from '../test/reactFlow.ts';
import { renderApp } from '../test/renderApp.tsx';
import { CONCEPTS_URL } from './TabHelp.tsx';

describe('tab help', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    mockReactFlowDom();
    mockApi(projectRoutes());
  });

  it.each([
    ['/x/tree', /goals hold batches, batches hold subtasks/i],
    ['/x/sessions', /each working session with Claude/i],
    ['/x/backlog', /per open session, project-wide, and unfiled/],
    ['/x/decisions', /superseded ones link to their replacement/],
  ])(
    '%s: collapsed, then expands to the text and the concepts link',
    async (path, text) => {
      renderApp(path);
      const toggle = await screen.findByRole('button', { name: /What is this\?/ });
      expect(toggle).toHaveAttribute('aria-expanded', 'false');
      expect(screen.queryByText(text)).toBeNull();
      expect(screen.queryByRole('link', { name: 'Concepts' })).toBeNull();
      fireEvent.click(toggle);
      expect(toggle).toHaveAttribute('aria-expanded', 'true');
      expect(screen.getByText(text)).toBeInTheDocument();
      const link = screen.getByRole('link', { name: 'Concepts' });
      expect(link).toHaveAttribute('href', CONCEPTS_URL);
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    },
  );
});
