// Left-to-right layered layout with dagre; positions are top-left corners,
// as React Flow expects.
import { Graph, layout as runLayout } from '@dagrejs/dagre';

import type { GraphEdge, GraphNode } from './tree.ts';

export const NODE_WIDTH = 260;
// Room for a blocked line and its hint under the title and meta.
export const NODE_HEIGHT = 128;

interface Box {
  width: number;
  height: number;
  x: number;
  y: number;
}

export interface Positioned {
  node: GraphNode;
  x: number;
  y: number;
}

export function layout(
  nodes: readonly GraphNode[],
  edges: readonly GraphEdge[],
): Positioned[] {
  // dagre fills in x and y (the centre) during layout.
  const graph = new Graph<object, Box, object>();
  graph.setGraph({ rankdir: 'LR', nodesep: 20, ranksep: 70, marginx: 16, marginy: 16 });
  graph.setDefaultEdgeLabel(() => ({}));
  for (const node of nodes) {
    graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT, x: 0, y: 0 });
  }
  for (const edge of edges) {
    graph.setEdge(edge.source, edge.target);
  }
  runLayout(graph);
  return nodes.map((node) => {
    const placed = graph.node(node.id);
    return { node, x: placed.x - NODE_WIDTH / 2, y: placed.y - NODE_HEIGHT / 2 };
  });
}
