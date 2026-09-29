// Groups a session's linked items by what happened to them. A disposition
// is what the close decided; with none, an item that is done or dropped now
// ended while linked (the close only disposes of open items).
import type { SessionItemEntry, SessionStatus } from '../api/types.gen.ts';

export type Outcome =
  | 'done'
  | 'dropped'
  | 'carry_over'
  | 'session_backlog'
  | 'project_backlog'
  | 'dropped_at_close'
  | 'in_progress'
  | 'unresolved';

export const OUTCOME_LABEL: Record<Outcome, string> = {
  done: 'Done during it',
  dropped: 'Dropped during it',
  carry_over: 'Carried over',
  session_backlog: "Parked in this session's backlog",
  project_backlog: 'Moved to the project backlog',
  dropped_at_close: 'Dropped at close',
  in_progress: 'Still open (session running)',
  unresolved: 'No disposition recorded',
};

const ORDER: readonly Outcome[] = [
  'done',
  'dropped',
  'carry_over',
  'session_backlog',
  'project_backlog',
  'dropped_at_close',
  'in_progress',
  'unresolved',
];

export interface OutcomeGroup {
  outcome: Outcome;
  label: string;
  entries: SessionItemEntry[];
}

export function outcomeOf(entry: SessionItemEntry, status: SessionStatus): Outcome {
  if (entry.disposition === 'dropped') {
    return 'dropped_at_close';
  }
  if (entry.disposition !== null) {
    return entry.disposition;
  }
  if (entry.item.category === 'done') {
    return 'done';
  }
  if (entry.item.category === 'dropped') {
    return 'dropped';
  }
  return status === 'open' ? 'in_progress' : 'unresolved';
}

// Non-empty groups in a fixed order; entries keep their link order.
export function groupByOutcome(
  entries: readonly SessionItemEntry[],
  status: SessionStatus,
): OutcomeGroup[] {
  const byOutcome = new Map<Outcome, SessionItemEntry[]>();
  for (const entry of entries) {
    const outcome = outcomeOf(entry, status);
    byOutcome.set(outcome, [...(byOutcome.get(outcome) ?? []), entry]);
  }
  return ORDER.flatMap((outcome) => {
    const grouped = byOutcome.get(outcome);
    return grouped === undefined
      ? []
      : [{ outcome, label: OUTCOME_LABEL[outcome], entries: grouped }];
  });
}
