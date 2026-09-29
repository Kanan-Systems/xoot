// Pure tree logic: the project root, done/dropped collapse, the focus root,
// what open backlog blocks, and graph building.
// Tree entries arrive in pre-order, so a parent is always seen before its
// children.
import type { BlockedEntry, ItemSummary, TreeEntry } from '../api/types.gen.ts';

// Keys never contain '@', so the project node cannot collide with an item.
export const PROJECT_ID = '@project';

export type Closed = 'done' | 'dropped';
export type HiddenCounts = Readonly<Partial<Record<Closed, number>>>;

export function closedCategory(item: ItemSummary): Closed | null {
  return item.category === 'done' || item.category === 'dropped' ? item.category : null;
}

// Where an entry hangs: its parent, or the project for goals and
// project-level backlog.
export function parentId(entry: TreeEntry): string {
  return entry.item.parent ?? PROJECT_ID;
}

export interface Collapsed {
  visible: TreeEntry[];
  // Per parent id: the done and dropped direct children that are hidden.
  hidden: ReadonlyMap<string, HiddenCounts>;
}

// keep names an entry that stays visible even when closed: the root.
export function collapseDone(
  entries: readonly TreeEntry[],
  showDone: boolean,
  keep: string | null = null,
): Collapsed {
  const gone = new Set<string>();
  const hidden = new Map<string, Partial<Record<Closed, number>>>();
  const visible: TreeEntry[] = [];
  for (const entry of entries) {
    const parent = parentId(entry);
    const closed = closedCategory(entry.item);
    if (gone.has(parent)) {
      gone.add(entry.item.key);
    } else if (!showDone && entry.item.key !== keep && closed !== null) {
      gone.add(entry.item.key);
      const counts = hidden.get(parent) ?? {};
      counts[closed] = (counts[closed] ?? 0) + 1;
      hidden.set(parent, counts);
    } else {
      visible.push(entry);
    }
  }
  return { visible, hidden };
}

// The root and everything below it; empty when the key is absent.
export function subtree(entries: readonly TreeEntry[], key: string): TreeEntry[] {
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

export interface Blocked {
  count: number;
  // What every one of is closed: a batch's subtasks, a goal's batches.
  children: 'subtasks' | 'batches';
  // The open backlog items sitting on the node, when the tree has them.
  backlog: readonly string[];
}

// Open backlog keys per holder, from the entries the tree returned.
export function openBacklog(entries: readonly TreeEntry[]): Map<string, string[]> {
  const byHolder = new Map<string, string[]>();
  for (const { item } of entries) {
    if (item.kind === 'backlog' && closedCategory(item) === null) {
      const holder = item.parent ?? PROJECT_ID;
      byHolder.set(holder, [...(byHolder.get(holder) ?? []), item.key]);
    }
  }
  return byHolder;
}

export function blockedOf(
  item: ItemSummary,
  counts: ReadonlyMap<string, number>,
  backlog: ReadonlyMap<string, readonly string[]>,
): Blocked | null {
  const count = counts.get(item.key);
  if (count === undefined || (item.kind !== 'goal' && item.kind !== 'batch')) {
    return null;
  }
  return {
    count,
    children: item.kind === 'goal' ? 'batches' : 'subtasks',
    backlog: backlog.get(item.key) ?? [],
  };
}

export function blockedLine(blocked: Blocked): string {
  return `all ${blocked.children} done · ${String(blocked.count)} backlog open`;
}

// Read-only: the dashboard never writes, so it says what to ask for.
export function blockedHint(key: string, blocked: Blocked): string {
  const target = blocked.backlog.length > 0 ? blocked.backlog.join(', ') : key;
  return `Ask Claude to cover or push ${target}`;
}

export function blockedCounts(blocked: readonly BlockedEntry[]): Map<string, number> {
  return new Map(blocked.map((entry) => [entry.key, entry.open_backlog]));
}

export type ItemNodeData = {
  item: ItemSummary;
  hidden: HiddenCounts;
  decisions: number;
  blocked: Blocked | null;
};

export type ProjectNodeData = {
  name: string;
  prefix: string;
  hidden: HiddenCounts;
};

export type GraphNode =
  | { id: string; type: 'item'; data: ItemNodeData }
  | { id: string; type: 'project'; data: ProjectNodeData };

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  rootMissing: boolean;
}

export interface GraphOptions {
  showDone: boolean;
  // A goal or batch as the root; null for the project-root tree.
  rootKey: string | null;
  project: { name: string; prefix: string };
  decisionCounts: ReadonlyMap<string, number>;
  blocked: ReadonlyMap<string, number>;
}

export function buildGraph(
  entries: readonly TreeEntry[],
  options: GraphOptions,
): Graph {
  const { rootKey } = options;
  const scoped = rootKey === null ? entries : subtree(entries, rootKey);
  const { visible, hidden } = collapseDone(scoped, options.showDone, rootKey);
  const backlog = openBacklog(scoped);
  const shown = new Set(visible.map((entry) => entry.item.key));
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  if (rootKey === null) {
    shown.add(PROJECT_ID);
    nodes.push({
      id: PROJECT_ID,
      type: 'project',
      data: { ...options.project, hidden: hidden.get(PROJECT_ID) ?? {} },
    });
  }
  for (const entry of visible) {
    const { key } = entry.item;
    nodes.push({
      id: key,
      type: 'item',
      data: {
        item: entry.item,
        hidden: hidden.get(key) ?? {},
        decisions: options.decisionCounts.get(key) ?? 0,
        blocked: blockedOf(entry.item, options.blocked, backlog),
      },
    });
    const parent = parentId(entry);
    if (key !== rootKey && shown.has(parent)) {
      edges.push({ id: `${parent}->${key}`, source: parent, target: key });
    }
  }
  return { nodes, edges, rootMissing: rootKey !== null && scoped.length === 0 };
}

export function countByOwner(
  decisions: readonly { owner: string | null }[],
): Map<string, number> {
  const counts = new Map<string, number>();
  for (const decision of decisions) {
    if (decision.owner !== null) {
      counts.set(decision.owner, (counts.get(decision.owner) ?? 0) + 1);
    }
  }
  return counts;
}
