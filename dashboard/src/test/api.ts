// A fake /api/v1 for component tests: responses keyed by path (without the
// query string), served through a stubbed fetch. Unknown paths are a 404.
import { vi } from 'vitest';

import type {
  BacklogsView,
  DecisionsView,
  ItemView,
  SessionView,
  SessionsView,
  TreeView,
} from '../api/types.gen.ts';
import { item, sampleTree } from './fixtures.ts';

export type Routes = Record<string, unknown>;

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export function urlOf(input: RequestInfo | URL): string {
  if (typeof input === 'string') {
    return input;
  }
  return input instanceof URL ? input.href : input.url;
}

// Installs the fake; a value that is a function is called on each request.
export function mockApi(routes: Routes) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = new URL(urlOf(input), 'http://t');
    const path = url.pathname.replace(/^\/api\/v1/, '');
    const route = routes[path];
    if (route === undefined) {
      return Promise.resolve(json(404, { error: 'NotFoundError', message: path }));
    }
    const body: unknown =
      typeof route === 'function' ? (route as () => unknown)() : route;
    return Promise.resolve(json(200, body));
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

export function treeView(): TreeView {
  return { project: 'x', nodes: sampleTree(), truncated: false };
}

export function itemView(key: string): ItemView {
  const summary = item(key, 'batch', 'x-1');
  return {
    item: {
      ...summary,
      body: `body of ${key}`,
      awaiting_decision: null,
      unfiled: false,
      created_at: '2026-09-28T00:00:00.000000Z',
      updated_at: '2026-09-28T00:00:00.000000Z',
    },
    children: { total: 0, by_category: {}, items: [], truncated: false },
    events: [],
    sessions: [],
    decisions: [],
  };
}

const SESSION_BASE = {
  client: 'code',
  started_at: '2026-09-28T10:00:00.000000Z',
} as const;

export function sessionsView(): SessionsView {
  return {
    project: 'x',
    truncated: false,
    sessions: [
      {
        ...SESSION_BASE,
        key: 'x-S2',
        title: 'open one',
        status: 'open',
        closed_at: null,
        linked_items: 2,
      },
      {
        ...SESSION_BASE,
        key: 'x-S1',
        title: 'closed one',
        status: 'closed',
        closed_at: '2026-09-28T11:00:00.000000Z',
        linked_items: 5,
      },
    ],
  };
}

export function sessionView(): SessionView {
  return {
    session: {
      ...SESSION_BASE,
      key: 'x-S1',
      title: 'closed one',
      status: 'closed',
      closed_at: '2026-09-28T11:00:00.000000Z',
    },
    summary: 'wrapped up',
    items: ['x-2', 'x-4', 'x-7'],
    linked: [
      { item: item('x-2', 'batch', 'x-1'), disposition: 'carry_over', captured: false },
      {
        item: item('x-4', 'subtask', 'x-2', 'done'),
        disposition: null,
        captured: false,
      },
      {
        item: item('x-7', 'subtask', null, 'backlogged'),
        disposition: 'session_backlog',
        captured: true,
      },
    ],
  };
}

export function backlogsView(): BacklogsView {
  const row = (key: string, holder: string | null) => ({
    ...item(key, 'subtask', null, 'backlogged'),
    backlog_session: holder,
    created_at: '2026-09-28T09:30:00.000000Z',
  });
  return {
    project: 'x',
    sessions: [
      {
        session: {
          ...SESSION_BASE,
          key: 'x-S2',
          title: 'open one',
          status: 'open',
          closed_at: null,
        },
        items: [row('x-9', 'x-S2')],
        truncated: false,
      },
    ],
    project_backlog: [row('x-10', null)],
    project_backlog_truncated: false,
    unfiled: [row('x-9', 'x-S2'), row('x-7', null)],
    unfiled_truncated: false,
  };
}

export function decisionsView(): DecisionsView {
  const base = { scope: null, supersedes: null, updated_at: 't', version: 1 };
  return {
    project: 'x',
    truncated: false,
    decisions: [
      {
        ...base,
        key: 'x-D2',
        title: 'new rule',
        status: 'locked',
        supersedes: 'x-D1',
        scope: 'x-1',
      },
      { ...base, key: 'x-D1', title: 'old rule', status: 'superseded' },
      { ...base, key: 'x-D3', title: 'later', status: 'deferred' },
    ],
  };
}

// Every endpoint the project views read, for prefix x.
export function projectRoutes(overrides: Routes = {}): Routes {
  return {
    '/projects': { projects: [{ key_prefix: 'x', name: 'x', aliases: [] }] },
    '/projects/x/changes': { latest_event_id: 1 },
    '/projects/x/tree': treeView(),
    '/projects/x/decisions': decisionsView(),
    '/projects/x/sessions': sessionsView(),
    '/projects/x/sessions/x-S1': sessionView(),
    '/projects/x/backlogs': backlogsView(),
    '/items/x-1': itemView('x-1'),
    '/items/x-2': itemView('x-2'),
    '/items/x-3': itemView('x-3'),
    '/items/x-9': itemView('x-9'),
    ...overrides,
  };
}
