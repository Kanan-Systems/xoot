// The LTR tree. Nodes are not draggable or selectable; onNodeClick is what
// gives React Flow's node wrappers pointer events (without a click handler
// it renders them with pointer-events: none, and clicks fall through to the
// pane). Item wrappers are focusable groups (a button role would hide the
// focus and badge buttons inside them): Enter or Space on one does what a
// click does. Double-click focuses a goal or batch, so it does not zoom.
// The project node only draws and is not focusable.
import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type NodeMouseHandler,
  type NodeTypes,
} from '@xyflow/react';
import { useCallback, useMemo, type KeyboardEvent } from 'react';

import type { TreeEntry } from '../api/types.gen.ts';
import { KIND } from '../lib/display.ts';
import { layout } from '../lib/layout.ts';
import { blockedLine, buildGraph, type Graph } from '../lib/tree.ts';
import { ItemNode, type ItemFlowNode } from './ItemNode.tsx';
import { ProjectNode, type ProjectFlowNode } from './ProjectNode.tsx';
import { NodeActionsContext } from './nodeActions.ts';

type FlowNode = ItemFlowNode | ProjectFlowNode;

const nodeTypes: NodeTypes = { item: ItemNode, project: ProjectNode };

// React Flow's controls take the dashboard's theme tokens (tree.css).
export const CONTROLS_CLASS = 'flow-controls';

export interface TreeCanvasProps {
  entries: readonly TreeEntry[];
  rootKey: string | null;
  project: { name: string; prefix: string };
  decisionCounts: ReadonlyMap<string, number>;
  blocked: ReadonlyMap<string, number>;
  showDone: boolean;
  collapsed: ReadonlySet<string>;
  onOpen: (key: string) => void;
  onFocus: (key: string) => void;
  onShowDone: () => void;
  onToggle: (key: string) => void;
}

export function TreeCanvas(props: TreeCanvasProps) {
  const { entries, rootKey, project, decisionCounts, blocked, showDone, collapsed } =
    props;
  const { onOpen, onFocus, onShowDone, onToggle } = props;
  // A toggle changes the graph, so the layout below is recomputed.
  const graph = useMemo(
    () =>
      buildGraph(entries, {
        showDone,
        rootKey,
        project,
        decisionCounts,
        blocked,
        collapsed,
      }),
    [entries, showDone, rootKey, project, decisionCounts, blocked, collapsed],
  );
  const flow = useMemo(() => toFlow(graph), [graph]);
  const activate = useCallback(
    (node: FlowNode) => {
      if (node.type === 'item') {
        onOpen(node.id);
      }
    },
    [onOpen],
  );
  const onNodeClick: NodeMouseHandler<FlowNode> = useCallback(
    (_event, node) => {
      activate(node);
    },
    [activate],
  );
  const onNodeDoubleClick: NodeMouseHandler<FlowNode> = useCallback(
    (_event, node) => {
      if (node.type === 'item' && ['goal', 'batch'].includes(node.data.item.kind)) {
        onFocus(node.id);
      }
    },
    [onFocus],
  );
  // Key events from a focused node wrapper bubble here; inner buttons keep
  // their own native Enter/Space.
  const onKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      const target = event.target;
      if (
        (event.key !== 'Enter' && event.key !== ' ') ||
        !(target instanceof HTMLElement) ||
        !target.classList.contains('react-flow__node')
      ) {
        return;
      }
      const node = flow.nodes.find((candidate) => candidate.id === target.dataset.id);
      if (node !== undefined) {
        event.preventDefault();
        activate(node);
      }
    },
    [flow.nodes, activate],
  );
  const actions = useMemo(
    () => ({ focus: onFocus, showDone: onShowDone, toggle: onToggle }),
    [onFocus, onShowDone, onToggle],
  );

  return (
    <NodeActionsContext.Provider value={actions}>
      {graph.rootMissing && (
        <p className="warning" role="alert">
          The focused item is gone.
        </p>
      )}
      <ReactFlow<FlowNode>
        key={rootKey ?? 'all'}
        nodes={flow.nodes}
        edges={flow.edges}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        nodesFocusable
        edgesFocusable={false}
        elementsSelectable={false}
        onNodeClick={onNodeClick}
        onNodeDoubleClick={onNodeDoubleClick}
        onKeyDown={onKeyDown}
        zoomOnDoubleClick={false}
        fitView
        minZoom={0.1}
      >
        <Background />
        <Controls className={CONTROLS_CLASS} showInteractive={false} />
      </ReactFlow>
    </NodeActionsContext.Provider>
  );
}

function toFlow(graph: Graph): { nodes: FlowNode[]; edges: Edge[] } {
  const nodes = layout(graph.nodes, graph.edges).map(({ node, x, y }): FlowNode => {
    const position = { x, y };
    if (node.type === 'project') {
      return {
        ...node,
        position,
        focusable: false,
        ariaLabel: `Project ${node.data.name}`,
      };
    }
    const { item, blocked, fold } = node.data;
    const held = blocked === null ? '' : `, ${blockedLine(blocked)}`;
    const folded =
      fold?.collapsed === true ? `, collapsed, ${String(fold.children)} children` : '';
    return {
      ...node,
      position,
      ariaLabel: `${KIND[item.kind].label}: ${item.title} (${item.key}), ${item.state}${held}${folded}. Press Enter for details`,
    };
  });
  const edges = graph.edges.map((edge) => ({ ...edge, selectable: false }));
  return { nodes, edges };
}
