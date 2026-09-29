// The decisions view: grouped by the goal their owner sits under, filtered
// by goal and by owner level. Group order is natural key order; within a
// group the API's newest-first order is kept.
import type { DecisionStatus, DecisionSummary } from '../api/types.gen.ts';
import { compareKeys, goalOf, ownerLevel, type OwnerLevel } from './keys.ts';

export const NO_GOAL = '';

export interface DecisionFilter {
  goal: string | null;
  level: OwnerLevel | null;
  status: DecisionStatus | null;
}

export interface DecisionGroup {
  // A goal key, or NO_GOAL for decisions whose owner is gone.
  goal: string;
  decisions: DecisionSummary[];
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

export function decisionGroups(
  decisions: readonly DecisionSummary[],
  filter: DecisionFilter,
): DecisionGroup[] {
  const groups = new Map<string, DecisionSummary[]>();
  for (const decision of decisions) {
    if (matches(decision, filter)) {
      const goal = goalKey(decision);
      groups.set(goal, [...(groups.get(goal) ?? []), decision]);
    }
  }
  return [...groups.entries()]
    .sort(([a], [b]) => (a === NO_GOAL ? 1 : b === NO_GOAL ? -1 : compareKeys(a, b)))
    .map(([goal, grouped]) => ({ goal, decisions: grouped }));
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
