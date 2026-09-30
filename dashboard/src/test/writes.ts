// Fixtures for write flows: the workflow, and the bodies write routes return.
import type {
  Category,
  ChangeEntry,
  ItemDetail,
  ItemUpdateOutput,
  PushOutput,
  WorkflowKindView,
  WorkflowView,
} from '../api/types.gen.ts';

const STATES: readonly Category[] = ['open', 'active', 'blocked', 'done', 'dropped'];

function kind(transitions: WorkflowKindView['transitions']): WorkflowKindView {
  return {
    states: STATES.map((name) => ({ name, category: name })),
    transitions,
    transitions_restricted: transitions !== null,
  };
}

// Every kind moves freely except the subtask, which restricts its moves.
export function workflowView(): WorkflowView {
  return {
    workflow: {
      goal: kind(null),
      batch: kind(null),
      backlog: kind(null),
      subtask: kind({
        open: ['active', 'dropped'],
        active: ['done', 'blocked'],
        blocked: ['active'],
        done: [],
        dropped: [],
      }),
    },
  };
}

export function detail(key: string, overrides: Partial<ItemDetail> = {}): ItemDetail {
  return {
    key,
    kind: 'batch',
    title: `title of ${key}`,
    state: 'open',
    category: 'open',
    parent: null,
    version: 2,
    body: '',
    awaiting_decision: null,
    found_on: null,
    covered_by: null,
    origin: null,
    aliases: [],
    created_at: '2026-09-28T00:00:00.000000Z',
    updated_at: '2026-09-28T00:00:00.000000Z',
    ...overrides,
  };
}

export const MOVE_CHANGE: ChangeEntry = {
  key: 'goal-1/batch-2',
  before: { key: 'goal-1/batch-2', parent: 'goal-1' },
  after: { key: 'goal-2/batch-2', parent: 'goal-2' },
};

export function updated(key: string, mode: ItemUpdateOutput['mode']): ItemUpdateOutput {
  return {
    project: 'x',
    mode,
    phase: 'applied',
    confirm_token: null,
    plan: null,
    item: detail(key),
  };
}

export function previewed(
  mode: ItemUpdateOutput['mode'],
  token = 'tok-1',
  changes: ChangeEntry[] = [MOVE_CHANGE],
): ItemUpdateOutput {
  return {
    project: 'x',
    mode,
    phase: 'preview',
    confirm_token: token,
    item: null,
    plan: { root: changes[0]?.key ?? '', changes },
  };
}

export function pushed(phase: PushOutput['phase'], token: string | null): PushOutput {
  const change: ChangeEntry = {
    key: 'goal-1/backlog-1',
    before: { key: 'goal-1/backlog-1', parent: 'goal-1' },
    after: { key: 'backlog-3', parent: null, number: 3 },
  };
  return {
    project: 'x',
    phase,
    confirm_token: token,
    item: null,
    plan: { root: change.key, changes: [change] },
  };
}

export const CONFLICT_DETAILS = {
  key: 'goal-1/batch-2',
  current_version: 3,
  changed_fields: ['title', 'state'],
  actors: [{ kind: 'claude', client: 'code' }],
};
