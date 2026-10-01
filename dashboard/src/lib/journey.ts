// Where an item was and where it goes, as indented staircases like the
// Decisions tab (goal, the batch under it, then the item), built from
// titles; a key shows only where its title is unknown. A drop has no
// destination: it is the dropped item with, indented, what drops with it.
// Nothing here renders a plan's raw fields.
import type { SubtreeOutput } from '../api/types.gen.ts';
import type { Titles } from './titles.ts';
import { kindOf, parentOf, rootChange } from './wording.ts';

export interface Step {
  depth: number;
  text: string;
  // The item's kind, on the line of the item itself.
  note: string | null;
}

export interface Journey {
  from: Step[];
  // Empty for a drop.
  to: Step[];
}

const NOTE = {
  goal: 'goal',
  batch: 'batch',
  subtask: 'subtask',
  backlog: 'backlog item',
} as const;

// A key and each key above it, outermost first.
function lineage(key: string | null): string[] {
  if (key === null) {
    return [];
  }
  const parts = key.split('/');
  return parts.map((_, index) => parts.slice(0, index + 1).join('/'));
}

function titled(key: string, titles: Titles): string {
  return titles.get(key) ?? key;
}

function place(parent: string | null, titles: Titles): Step[] {
  return lineage(parent).map((key, depth) => ({
    depth,
    text: titled(key, titles),
    note: null,
  }));
}

function own(key: string, depth: number, titles: Titles): Step {
  const kind = kindOf(key);
  return { depth, text: titled(key, titles), note: kind === null ? null : NOTE[kind] };
}

// A backlog item lands in a list, named by its holder's kind; work lands as
// itself under its new parent.
function landing(key: string, parent: string | null, titles: Titles): Step {
  const depth = lineage(parent).length;
  if (kindOf(key) !== 'backlog') {
    return own(key, depth, titles);
  }
  const holder = parent === null ? 'project' : (kindOf(parent) ?? 'parent');
  return { depth, text: `(${holder} backlog)`, note: null };
}

export function moveJourney(
  key: string,
  parent: string | null,
  titles: Titles,
): Journey {
  const from = parentOf(key);
  return {
    from: [...place(from, titles), own(key, lineage(from).length, titles)],
    to: [...place(parent, titles), landing(key, parent, titles)],
  };
}

// A push names its new parent only in the plan.
export function pushJourney(key: string, plan: SubtreeOutput, titles: Titles): Journey {
  const parent = rootChange(plan, key)?.after.parent;
  return moveJourney(key, typeof parent === 'string' ? parent : null, titles);
}

export function dropJourney(key: string, plan: SubtreeOutput, titles: Titles): Journey {
  const base = lineage(key).length;
  const along = plan.changes
    .map((change) => change.key)
    .filter((changed) => changed.startsWith(`${key}/`))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  return {
    from: [
      own(key, 0, titles),
      ...along.map((changed) => own(changed, lineage(changed).length - base, titles)),
    ],
    to: [],
  };
}
