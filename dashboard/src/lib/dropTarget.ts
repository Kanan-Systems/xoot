// What a drop in the tree means. A candidate counts when the pointer is
// inside it, or when the dragged node covers a real share of it: xyflow's
// own intersection test counts a node that merely touches the dragged one,
// so a drop in the gap between nodes would graze a neighbour. Of several,
// one under the pointer wins, else the one overlapped most. A collapsed goal
// or batch is drawn, so it is a target: only its children are hidden, and
// nodes that are not drawn are never candidates. Every rectangle and the
// pointer must be in flow coordinates (see flowDrop.ts).
import type { ItemSummary } from '../api/types.gen.ts';
import { parentKindOf } from './itemRules.ts';

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface Placed {
  item: ItemSummary;
  rect: Rect;
}

export type DropResult = { ok: true; parent: string } | { ok: false; reason: string };

// One candidate as judged, for the debug log.
export interface Judged {
  key: string;
  kind: string;
  rect: Rect;
  overlap: number;
  pointerInside: boolean;
  allowed: boolean;
  matches: boolean;
}

export interface Decision {
  result: DropResult;
  judged: Judged[];
  why: string;
}

// A share of the smaller node's area, so a small node dropped fully inside
// a large one counts, and a corner or an edge graze does not.
export const MIN_OVERLAP = 0.25;

export const NO_TARGET = 'Drop it on a batch or goal to move it.';

export function overlapArea(a: Rect, b: Rect): number {
  const width = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
  const height = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
  return width > 0 && height > 0 ? width * height : 0;
}

export function contains(rect: Rect, point: Point): boolean {
  return (
    point.x >= rect.x &&
    point.x < rect.x + rect.width &&
    point.y >= rect.y &&
    point.y < rect.y + rect.height
  );
}

function enough(a: Rect, b: Rect, overlap: number): boolean {
  const smaller = Math.min(a.width * a.height, b.width * b.height);
  return smaller > 0 && overlap >= MIN_OVERLAP * smaller;
}

function better(a: Judged, b: Judged | null): boolean {
  if (b === null) {
    return true;
  }
  if (a.pointerInside !== b.pointerInside) {
    return a.pointerInside;
  }
  return a.overlap > b.overlap;
}

export function decideDrop(
  dragged: Placed,
  candidates: readonly Placed[],
  pointer: Point | null,
): Decision {
  const want = parentKindOf(dragged.item.kind);
  if (want === null) {
    const reason = 'Only batches and subtasks can be moved.';
    return { result: { ok: false, reason }, judged: [], why: reason };
  }
  let winner: Judged | null = null;
  const judged: Judged[] = [];
  for (const { item, rect } of candidates) {
    const overlap = overlapArea(dragged.rect, rect);
    const pointerInside = pointer !== null && contains(rect, pointer);
    const allowed = item.kind === want && item.key !== dragged.item.key;
    const matches = allowed && (pointerInside || enough(dragged.rect, rect, overlap));
    const one = {
      key: item.key,
      kind: item.kind,
      rect,
      overlap,
      pointerInside,
      allowed,
      matches,
    };
    judged.push(one);
    if (matches && better(one, winner)) {
      winner = one;
    }
  }
  if (winner === null) {
    return {
      result: { ok: false, reason: NO_TARGET },
      judged,
      why: 'no candidate matched',
    };
  }
  if (winner.key === dragged.item.parent) {
    const reason = `${dragged.item.key} is already there.`;
    return {
      result: { ok: false, reason },
      judged,
      why: `${winner.key} is the current parent`,
    };
  }
  const how = winner.pointerInside ? 'the pointer is inside it' : 'the largest overlap';
  return {
    result: { ok: true, parent: winner.key },
    judged,
    why: `${winner.key}: ${how}`,
  };
}

export function dropTarget(
  dragged: Placed,
  candidates: readonly Placed[],
  pointer: Point | null = null,
): DropResult {
  return decideDrop(dragged, candidates, pointer).result;
}
