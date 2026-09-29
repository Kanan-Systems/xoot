// A fake /api/v1 for component tests: responses keyed by path (without the
// query string, percent-decoded as the server decodes it), served through
// a stubbed fetch. Unknown paths are a 404.
import { vi } from 'vitest';

import type {
  BacklogRow,
  BacklogView,
  DecisionsView,
  ItemView,
  TreeView,
} from '../api/types.gen.ts';
import {
  B1,
  B1_BACKLOG,
  G1,
  G1_BACKLOG,
  item,
  P_BACKLOG,
  sampleTree,
} from './fixtures.ts';

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
    const path = decodeURIComponent(url.pathname.replace(/^\/api\/v1/, ''));
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
  return {
    project: 'x',
    nodes: sampleTree(),
    truncated: false,
    blocked: [{ key: B1, open_backlog: 1 }],
  };
}

export function itemView(key: string): ItemView {
  const found = sampleTree().find((node) => node.item.key === key)?.item;
  const summary = found ?? item(key, 'batch', G1);
  return {
    item: {
      ...summary,
      body: `body of ${key}`,
      awaiting_decision: null,
      found_on: null,
      covered_by: null,
      origin: null,
      aliases: [],
      created_at: '2026-09-28T00:00:00.000000Z',
      updated_at: '2026-09-28T00:00:00.000000Z',
    },
    children: { total: 0, by_category: {}, items: [], truncated: false },
    events: [],
    decisions: [],
  };
}

function row(
  key: string,
  level: BacklogRow['level'],
  parent: string | null,
): BacklogRow {
  return {
    ...item(key, 'backlog', parent),
    level,
    found_on: parent,
    created_at: '2026-09-28T09:30:00.000000Z',
    why: `why ${key}`,
  };
}

// As the API orders it: project level first, then by key.
export function backlogView(): BacklogView {
  return {
    project: 'x',
    truncated: false,
    items: [
      row(P_BACKLOG, 'project', null),
      row(G1_BACKLOG, 'goal', G1),
      row(B1_BACKLOG, 'batch', B1),
    ],
  };
}

export function decisionsView(): DecisionsView {
  const base = { supersedes: null, updated_at: 't', version: 1 };
  return {
    project: 'x',
    truncated: false,
    decisions: [
      {
        ...base,
        key: 'goal-1/batch-1/decision-2',
        title: 'new rule',
        status: 'locked',
        supersedes: 'goal-1/decision-1',
        owner: B1,
      },
      {
        ...base,
        key: 'goal-1/decision-1',
        title: 'old rule',
        status: 'superseded',
        owner: G1,
      },
      {
        ...base,
        key: 'goal-2/batch-1/subtask-1/decision-1',
        title: 'later',
        status: 'deferred',
        owner: 'goal-2/batch-1/subtask-1',
      },
    ],
  };
}

// Every endpoint the project views read, for prefix x.
export function projectRoutes(overrides: Routes = {}): Routes {
  const items = Object.fromEntries(
    sampleTree().map((node) => [
      `/projects/x/items/${node.item.key}`,
      itemView(node.item.key),
    ]),
  );
  return {
    '/projects': { projects: [{ key_prefix: 'x', name: 'Xproj', aliases: [] }] },
    '/projects/x/changes': { latest_event_id: 1 },
    '/projects/x/tree': treeView(),
    '/projects/x/decisions': decisionsView(),
    '/projects/x/backlog': backlogView(),
    ...items,
    ...overrides,
  };
}
