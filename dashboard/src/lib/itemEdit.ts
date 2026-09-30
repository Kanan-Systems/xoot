// Pure rules of the drawer editor: which states it offers and what a Save
// sends. The server enforces all of it again.
import type {
  Category,
  ItemUpdateRequest,
  StateSpec,
  WorkflowKindView,
} from '../api/types.gen.ts';
import { bodyProblem, titleProblem } from './limits.ts';

// Unrestricted kinds offer every state; a restricted kind offers the current
// state and the moves allowed from it. Unknown workflow: the current state.
export function stateOptions(
  workflow: WorkflowKindView | undefined,
  current: string,
  category: Category | null,
): StateSpec[] {
  const currentSpec: StateSpec | undefined = workflow?.states.find(
    (spec) => spec.name === current,
  );
  const fallback: StateSpec[] = [{ name: current, category: category ?? 'open' }];
  if (workflow === undefined) {
    return fallback;
  }
  if (workflow.transitions === null) {
    return currentSpec === undefined
      ? [...fallback, ...workflow.states]
      : workflow.states;
  }
  const allowed = new Set([current, ...(workflow.transitions[current] ?? [])]);
  const offered = workflow.states.filter((spec) => allowed.has(spec.name));
  return currentSpec === undefined ? [...fallback, ...offered] : offered;
}

export interface Draft {
  title: string;
  body: string;
  state: string;
}

export interface Base extends Draft {
  version: number;
  hasChildren: boolean;
}

export type EditResult =
  | { kind: 'unchanged' }
  | { kind: 'problem'; message: string }
  | { kind: 'send'; request: ItemUpdateRequest };

export const DROP_ALONE =
  'Dropping an item with children is saved on its own: change only the state, save, then edit the rest.';

// The fields that changed, based on the version the edit started from.
export function editRequest(
  base: Base,
  draft: Draft,
  stateCategory: Category | undefined,
): EditResult {
  const request: ItemUpdateRequest = { expected_version: base.version };
  if (draft.title !== base.title) {
    request.title = draft.title;
  }
  if (draft.body !== base.body) {
    request.body = draft.body;
  }
  if (draft.state !== base.state) {
    request.state = draft.state;
  }
  if (Object.keys(request).length === 1) {
    return { kind: 'unchanged' };
  }
  const problem =
    (request.title === undefined ? null : titleProblem(draft.title)) ??
    (request.body === undefined ? null : bodyProblem(draft.body));
  if (problem !== null) {
    return { kind: 'problem', message: problem };
  }
  const drop = request.state !== undefined && stateCategory === 'dropped';
  if (drop && base.hasChildren && Object.keys(request).length > 2) {
    return { kind: 'problem', message: DROP_ALONE };
  }
  return { kind: 'send', request };
}
