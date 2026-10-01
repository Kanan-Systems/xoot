// The drawer's history while the tree (where titles come from) is still
// loading: it shows keys at once, then titles once the tree is in, and
// passes through no other text on the way (no blank, no partial line).
import { screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { itemView, mockApi, projectRoutes, urlOf } from '../test/api.ts';
import { B1, B2, S3 } from '../test/fixtures.ts';
import { renderApp } from '../test/renderApp.tsx';

const MOVED = {
  action: 'update' as const,
  actor_kind: 'user' as const,
  client: 'dashboard' as const,
  created_at: '2026-09-28T10:15:30.000000Z',
  redacted: false,
  changed: ['key', 'parent', 'version'],
  before: { key: 'goal-1/batch-1/subtask-7', parent: B1, version: 1 },
  after: { key: S3, parent: B2, version: 2 },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('history while the tree loads', () => {
  it('shows keys at once, then titles, and nothing in between', async () => {
    const view = { ...itemView(S3), events: [MOVED] };
    const inner = mockApi(projectRoutes({ [`/projects/x/items/${S3}`]: view }));
    let release = () => {};
    const treeHeld = new Promise<void>((resolve) => {
      release = resolve;
    });
    vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
      if (urlOf(input).includes('/projects/x/tree')) {
        await treeHeld;
      }
      return inner(input, init);
    });
    renderApp(`/x/backlog?item=${encodeURIComponent(S3)}`);
    const line = await screen.findByText(/· moved /);
    const seen = [line.textContent];
    const observer = new MutationObserver(() => {
      const text = document.querySelector('.history li')?.textContent ?? '';
      if (text !== seen[seen.length - 1]) {
        seen.push(text);
      }
    });
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
    });
    expect(seen[0]).toBe(
      `user · dashboard · 2026-09-28 10:15 · moved from ${B1} to ${B2}`,
    );
    release();
    await waitFor(() => {
      expect(seen[seen.length - 1]).toBe(
        `user · dashboard · 2026-09-28 10:15 · moved from title of ${B1} to title of ${B2}`,
      );
    });
    observer.disconnect();
    expect(seen).toHaveLength(2);
  });
});
