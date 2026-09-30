// The decisions view: grouped goal > batch > subtask by the owner's key,
// filtered by goal, owner level and status. Headings sort in natural key
// order; under each, the API's newest-first order is kept.
import type { DecisionStatus, DecisionSummary } from '../api/types.gen.ts';
import {
  batchOf,
  compareKeys,
  goalOf,
  ownerLevel,
  subtaskOf,
  type OwnerLevel,
} from './keys.ts';

export const NO_GOAL = '';

export interface DecisionFilter {
  goal: string | null;
  level: OwnerLevel | null;
  status: DecisionStatus | null;
}

// One owner's heading: a goal, a batch or a subtask, with the decisions
// made on it and the headings of the owners below it.
export interface DecisionNode {
  key: string;
  level: OwnerLevel;
  decisions: DecisionSummary[];
  children: DecisionNode[];
}

export interface DecisionHierarchy {
  goals: DecisionNode[];
  // Decisions whose owner is gone: the last group.
  ownerless: DecisionSummary[];
}

function goalKey(decision: DecisionSummary): string {
  return decision.owner === null ? NO_GOAL : (goalOf(decision.owner) ?? NO_GOAL);
}

export function matches(decision: DecisionSummary, filter: DecisionFilter): boolean {
  const level = decision.owner === null ? null : ownerLevel(decision.owner);
  return (
    (filter.goal === null || goalKey(decision) === filter.goal) &&
    (filter.level === null || level === filter.level) &&
    (filter.status === null || decision.status === filter.status)
  );
}

function sorted(nodes: Iterable<DecisionNode>): DecisionNode[] {
  return [...nodes]
    .sort((a, b) => compareKeys(a.key, b.key))
    .map((node) => ({ ...node, children: sorted(node.children) }));
}

// Grouped goal > batch > subtask by the owner's key; only headings with a
// matching decision at or below them appear.
export function decisionHierarchy(
  decisions: readonly DecisionSummary[],
  filter: DecisionFilter,
): DecisionHierarchy {
  const nodes = new Map<string, DecisionNode>();
  const goals: DecisionNode[] = [];
  const ownerless: DecisionSummary[] = [];
  const nodeOf = (key: string, level: OwnerLevel, parent: DecisionNode | null) => {
    const known = nodes.get(key);
    if (known !== undefined) {
      return known;
    }
    const node: DecisionNode = { key, level, decisions: [], children: [] };
    nodes.set(key, node);
    (parent === null ? goals : parent.children).push(node);
    return node;
  };
  for (const decision of decisions) {
    if (!matches(decision, filter)) {
      continue;
    }
    const goal = decision.owner === null ? null : goalOf(decision.owner);
    if (decision.owner === null || goal === null) {
      ownerless.push(decision);
      continue;
    }
    let node = nodeOf(goal, 'goal', null);
    const batch = batchOf(decision.owner);
    if (batch !== null) {
      node = nodeOf(batch, 'batch', node);
      const subtask = subtaskOf(decision.owner);
      if (subtask !== null) {
        node = nodeOf(subtask, 'subtask', node);
      }
    }
    node.decisions.push(decision);
  }
  return { goals: sorted(goals), ownerless };
}

// How many decisions a heading holds, below it included.
export function countOf(node: DecisionNode): number {
  return node.children.reduce(
    (sum, child) => sum + countOf(child),
    node.decisions.length,
  );
}

// The goals any decision sits under, for the filter.
export function decisionGoals(decisions: readonly DecisionSummary[]): string[] {
  const goals = new Set(decisions.map(goalKey));
  goals.delete(NO_GOAL);
  return [...goals].sort(compareKeys);
}

// Which decision supersedes each one, from the supersedes links.
export function supersededBy(
  decisions: readonly DecisionSummary[],
): Map<string, string> {
  const next = new Map<string, string>();
  for (const decision of decisions) {
    if (decision.supersedes !== null) {
      next.set(decision.supersedes, decision.key);
    }
  }
  return next;
}
