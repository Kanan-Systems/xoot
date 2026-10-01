// Armed dragging in the tree, as a pure state machine. A double-click arms
// one batch or subtask; only the armed node can be dragged. A drop onto an
// allowed parent waits for the user's confirmation; nothing is sent before
// it. Confirm, Cancel, Escape and a click on empty canvas all end the move.
import type { ItemSummary } from '../api/types.gen.ts';
import { isMovable } from './itemRules.ts';

export interface PendingMove {
  item: ItemSummary;
  parent: string;
  // The item and everything under it when it was dropped: the only set a
  // returned plan may move without being shown again.
  keys: readonly string[];
}

export interface DragState {
  armed: string | null;
  pending: PendingMove | null;
}

export type DragEvent =
  | { type: 'arm'; item: ItemSummary }
  | { type: 'disarm' }
  | { type: 'drop'; item: ItemSummary; parent: string; keys: readonly string[] }
  | { type: 'confirm' }
  | { type: 'cancel' };

export const IDLE: DragState = { armed: null, pending: null };

export function dragReducer(state: DragState, event: DragEvent): DragState {
  switch (event.type) {
    case 'arm':
      // Goals, backlog items and the project never move by dragging; a
      // move waiting for confirmation is not replaced by arming another.
      if (state.pending !== null || !isMovable(event.item.kind)) {
        return state;
      }
      return { armed: event.item.key, pending: null };
    case 'drop':
      return state.armed === event.item.key && state.pending === null
        ? {
            armed: state.armed,
            pending: { item: event.item, parent: event.parent, keys: event.keys },
          }
        : state;
    case 'disarm':
    case 'confirm':
    case 'cancel':
      return IDLE;
  }
}

// The item's key and every key below it in the tree.
export function subtreeKeys(
  key: string,
  entries: readonly { item: { key: string } }[],
): string[] {
  return [
    key,
    ...entries.flatMap(({ item }) =>
      item.key.startsWith(`${key}/`) ? [item.key] : [],
    ),
  ];
}

// True only when a plan changes exactly the confirmed items: a count match
// is not enough, since one child can leave and another arrive in between.
export function sameKeys(
  changes: readonly { key: string }[],
  keys: readonly string[],
): boolean {
  const planned = new Set(changes.map((change) => change.key));
  const confirmed = new Set(keys);
  return (
    planned.size === changes.length &&
    planned.size === confirmed.size &&
    [...planned].every((key) => confirmed.has(key))
  );
}
