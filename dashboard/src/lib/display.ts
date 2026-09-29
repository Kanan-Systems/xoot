// How kinds and categories look. Every kind and category has an icon and a
// text label as well as a colour class, so colour is never the only signal.
import type { Category, DecisionStatus, ItemKind } from '../api/types.gen.ts';
import type { OwnerLevel } from './keys.ts';

export interface Glyph {
  icon: string;
  label: string;
}

export const KIND: Record<ItemKind, Glyph> = {
  goal: { icon: '◎', label: 'Goal' },
  batch: { icon: '▤', label: 'Batch' },
  subtask: { icon: '•', label: 'Subtask' },
  backlog: { icon: '⚑', label: 'Backlog' },
};

export const KINDS: readonly ItemKind[] = ['goal', 'batch', 'subtask', 'backlog'];

export const CATEGORY: Record<Category, Glyph> = {
  open: { icon: '○', label: 'Open' },
  active: { icon: '▶', label: 'Active' },
  blocked: { icon: '■', label: 'Blocked' },
  awaiting_input: { icon: '?', label: 'Awaiting input' },
  done: { icon: '✓', label: 'Done' },
  dropped: { icon: '✕', label: 'Dropped' },
};

export const CATEGORIES = Object.keys(CATEGORY) as Category[];

export const DECISION_STATUS: Record<DecisionStatus, Glyph> = {
  locked: { icon: '■', label: 'Locked' },
  deferred: { icon: '◇', label: 'Deferred' },
  superseded: { icon: '↷', label: 'Superseded' },
};

export const OWNER_LEVEL: Record<OwnerLevel, string> = {
  goal: 'Goal',
  batch: 'Batch',
  subtask: 'Subtask',
};

const UNKNOWN: Glyph = { icon: '·', label: 'Unknown state' };

export function categoryGlyph(category: Category | null): Glyph {
  return category === null ? UNKNOWN : CATEGORY[category];
}

export function categoryClass(category: Category | null): string {
  return `cat cat-${category ?? 'unknown'}`;
}

export const TITLE_MAX = 60;

export interface Shortened {
  text: string;
  truncated: boolean;
}

// Cuts on code points, so a surrogate pair is never split.
export function truncate(text: string, max: number = TITLE_MAX): Shortened {
  const chars = Array.from(text);
  if (chars.length <= max) {
    return { text, truncated: false };
  }
  return { text: `${chars.slice(0, max - 1).join('')}…`, truncated: true };
}

// A stored timestamp as "YYYY-MM-DD HH:MM" (UTC, as stored).
export function when(value: string): string {
  return value.slice(0, 16).replace('T', ' ');
}

// How long ago, in whole seconds, as the live indicator shows it.
export function ago(seconds: number): string {
  if (seconds < 60) {
    return `${String(seconds)} s ago`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${String(minutes)} min ago`;
  }
  return `${String(Math.floor(minutes / 60))} h ago`;
}
