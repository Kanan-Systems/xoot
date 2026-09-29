// Pure tree logic: done/dropped collapse, focus mode and graph building.
// Tree entries arrive in pre-order, so a parent is always seen before its
// children.
import type { Category, ItemSummary, TreeEntry } from '../api/types.gen.ts';

export const UNFILED_ID = 'unfiled';
export const ROOT_ID = '';

const TERMINAL: ReadonlySet<Category> = new Set<Category>(['done', 'dropped']);

export function isTerminal(item: ItemSummary): boolean {
  return item.category !== null && TERMINAL.has(item.category);
}

// Where an entry hangs: its parent, the unfiled group, or the top level.
export function parentId(entry: TreeEntry): string {
  if (entry.item.parent !== null) {
    return entry.item.parent;
  }
  return entry.unfiled ? UNFILED_ID : ROOT_ID;
}

export interface Collapsed {
  visible: TreeEntry[];
  // Per parent id: how many done or dropped direct children are hidden.
  hiddenDone: ReadonlyMap<string, number>;
}

// keep names an entry that stays visible even when done: the focus root.
export function collapseDone(
  entries: readonly TreeEntry[],
  showDone: boolean,
  keep: string | null = null,
): Collapsed {
  const hidden = new Set<string>();
  const hiddenDone = new Map<string, number>();
  const visible: TreeEntry[] = [];
  for (const entry of entries) {
    const parent = parentId(entry);
    if (hidden.has(parent)) {
      hidden.add(entry.item.key);
    } else if (!showDone && entry.item.key !== keep && isTerminal(entry.item)) {
      hidden.add(entry.item.key);
      hiddenDone.set(parent, (hiddenDone.get(parent) ?? 0) + 1);
    } else {
      visible.push(entry);
    }
  }
  return { visible, hiddenDone };
}

// The focus root and everything below it; empty when the key is absent.
export function focusSubtree(entries: readonly TreeEntry[], key: string): TreeEntry[] {
  const inside = new Set<string>([key]);
  const result: TreeEntry[] = [];
  for (const entry of entries) {
    if (entry.item.key === key || inside.has(parentId(entry))) {
      inside.add(entry.item.key);
      result.push(entry);
    }
  }
  return result;
}

export type ItemNodeData = {
  item: ItemSummary;
  hiddenDone: number;
  decisions: number;
  highlighted: boolean;
  dimmed: boolean;
};

export type UnfiledNodeData = {
  count: number;
  hiddenDone: number;
  dimmed: boolean;
};

export type GraphNode =
  | { id: string; type: 'item'; data: ItemNodeData }
  | { id: string; type: 'unfiled'; data: UnfiledNodeData };

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  hiddenTopLevel: number;
  focusMissing: boolean;
}

export interface GraphOptions {
  showDone: boolean;
  focusKey: string | null;
  decisionCounts: ReadonlyMap<string, number>;
  highlight: ReadonlySet<string> | null;
}

export function buildGraph(
  entries: readonly TreeEntry[],
  options: GraphOptions,
): Graph {
  const scoped =
    options.focusKey === null ? entries : focusSubtree(entries, options.focusKey);
  const focusRoot = options.focusKey;
  const { visible, hiddenDone } = collapseDone(scoped, options.showDone, focusRoot);
  const shown = new Set(visible.map((entry) => entry.item.key));
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  let unfiled = 0;
  for (const entry of visible) {
    const key = entry.item.key;
    const parent = key === focusRoot ? ROOT_ID : parentId(entry);
    const state = overlay(key, options.highlight);
    nodes.push({
      id: key,
      type: 'item',
      data: {
        item: entry.item,
        hiddenDone: hiddenDone.get(key) ?? 0,
        decisions: options.decisionCounts.get(key) ?? 0,
        ...state,
      },
    });
    if (parent === UNFILED_ID) {
      unfiled += 1;
    }
    if (parent === UNFILED_ID || shown.has(parent)) {
      edges.push({ id: `${parent}->${key}`, source: parent, target: key });
    }
  }
  const unfiledHidden = hiddenDone.get(UNFILED_ID) ?? 0;
  if (unfiled > 0 || unfiledHidden > 0) {
    nodes.push({
      id: UNFILED_ID,
      type: 'unfiled',
      data: {
        count: unfiled,
        hiddenDone: unfiledHidden,
        dimmed: options.highlight !== null,
      },
    });
  }
  return {
    nodes,
    edges,
    hiddenTopLevel: hiddenDone.get(ROOT_ID) ?? 0,
    focusMissing: focusRoot !== null && scoped.length === 0,
  };
}

export interface OverlayState {
  highlighted: boolean;
  dimmed: boolean;
}

// With a session selected, its items are highlighted and the rest dimmed.
export function overlay(
  key: string,
  highlight: ReadonlySet<string> | null,
): OverlayState {
  if (highlight === null) {
    return { highlighted: false, dimmed: false };
  }
  const linked = highlight.has(key);
  return { highlighted: linked, dimmed: !linked };
}

export function countByScope(
  decisions: readonly { scope: string | null }[],
): Map<string, number> {
  const counts = new Map<string, number>();
  for (const decision of decisions) {
    if (decision.scope !== null) {
      counts.set(decision.scope, (counts.get(decision.scope) ?? 0) + 1);
    }
  }
  return counts;
}
