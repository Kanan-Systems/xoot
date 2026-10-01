// What a drop in the tree means. xyflow's intersection test counts a node
// that merely touches the dragged one, so a drop in the gap between nodes
// proposed a move to whichever neighbour it grazed. A target now needs a
// real overlap, and of several the one overlapped most wins.
import type { ItemSummary } from '../api/types.gen.ts';
import { parentKindOf } from './itemRules.ts';

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Placed {
  item: ItemSummary;
  rect: Rect;
}

export type DropResult = { ok: true; parent: string } | { ok: false; reason: string };

// A share of the smaller node's area, so a small node dropped fully inside
// a large one counts, and a corner or an edge graze does not.
export const MIN_OVERLAP = 0.25;

export const NO_TARGET = 'Drop it on a batch or goal to move it.';

export function overlapArea(a: Rect, b: Rect): number {
  const width = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
  const height = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
  return width > 0 && height > 0 ? width * height : 0;
}

function enough(a: Rect, b: Rect, overlap: number): boolean {
  const smaller = Math.min(a.width * a.height, b.width * b.height);
  return smaller > 0 && overlap >= MIN_OVERLAP * smaller;
}

export function dropTarget(dragged: Placed, candidates: readonly Placed[]): DropResult {
  const want = parentKindOf(dragged.item.kind);
  if (want === null) {
    return { ok: false, reason: 'Only batches and subtasks can be moved.' };
  }
  let best: { key: string; overlap: number } | null = null;
  for (const { item, rect } of candidates) {
    const overlap = overlapArea(dragged.rect, rect);
    if (
      item.kind === want &&
      item.key !== dragged.item.key &&
      enough(dragged.rect, rect, overlap) &&
      (best === null || overlap > best.overlap)
    ) {
      best = { key: item.key, overlap };
    }
  }
  if (best === null) {
    return { ok: false, reason: NO_TARGET };
  }
  if (best.key === dragged.item.parent) {
    return { ok: false, reason: `${dragged.item.key} is already there.` };
  }
  return { ok: true, parent: best.key };
}
