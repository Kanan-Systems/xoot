// The LTR item tree. Nodes are not draggable or selectable; onNodeClick is
// what gives React Flow's node wrappers pointer events (without a click
// handler it renders them with pointer-events: none, and clicks fall through
// to the pane). The wrappers are focusable groups (a button role would hide
// the focus and done buttons inside them): Enter or Space on one does what a
// click does. Double-click focuses a goal or batch, so it does not zoom.
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
import { buildGraph, type Graph } from '../lib/tree.ts';
import { ItemNode, type ItemFlowNode } from './ItemNode.tsx';
import { UnfiledNode, type UnfiledFlowNode } from './UnfiledNode.tsx';
import { NodeActionsContext } from './nodeActions.ts';

type FlowNode = ItemFlowNode | UnfiledFlowNode;

const nodeTypes: NodeTypes = { item: ItemNode, unfiled: UnfiledNode };

export interface TreeCanvasProps {
  entries: readonly TreeEntry[];
  rootKey: string | null;
  decisionCounts: ReadonlyMap<string, number>;
  highlight: ReadonlySet<string> | null;
  showDone: boolean;
  unfiledOpen: boolean;
  onOpen: (key: string) => void;
  onFocus: (key: string) => void;
  onShowDone: () => void;
  onToggleUnfiled: () => void;
}

export function TreeCanvas(props: TreeCanvasProps) {
  const { entries, rootKey, decisionCounts, highlight, showDone, unfiledOpen } = props;
  const { onOpen, onFocus, onShowDone, onToggleUnfiled } = props;
  const graph = useMemo(
    () =>
      buildGraph(entries, {
        showDone,
        focusKey: rootKey,
        decisionCounts,
        highlight,
        unfiledOpen,
      }),
    [entries, showDone, rootKey, decisionCounts, highlight, unfiledOpen],
  );
  const flow = useMemo(() => toFlow(graph), [graph]);
  const activate = useCallback(
    (node: FlowNode) => {
      if (node.type === 'unfiled') {
        onToggleUnfiled();
      } else {
        onOpen(node.id);
      }
    },
    [onOpen, onToggleUnfiled],
  );
  const onNodeClick: NodeMouseHandler<FlowNode> = useCallback(
    (_event, node) => {
      activate(node);
    },
    [activate],
  );
  const onNodeDoubleClick: NodeMouseHandler<FlowNode> = useCallback(
    (_event, node) => {
      if (node.type === 'item' && node.data.item.kind !== 'subtask') {
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
    () => ({ focus: onFocus, showDone: onShowDone }),
    [onFocus, onShowDone],
  );

  return (
    <NodeActionsContext.Provider value={actions}>
      {graph.focusMissing && (
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
        <Controls showInteractive={false} />
      </ReactFlow>
    </NodeActionsContext.Provider>
  );
}

function toFlow(graph: Graph): { nodes: FlowNode[]; edges: Edge[] } {
  const nodes = layout(graph.nodes, graph.edges).map(({ node, x, y }): FlowNode => {
    const position = { x, y };
    if (node.type === 'unfiled') {
      return {
        ...node,
        position,
        ariaLabel: `Unfiled: ${String(node.data.count)} subtasks, ${
          node.data.open
            ? 'shown. Press Enter to collapse'
            : 'collapsed. Press Enter to expand'
        }`,
        domAttributes: { 'aria-expanded': node.data.open },
      };
    }
    const { item } = node.data;
    return {
      ...node,
      position,
      ariaLabel: `${KIND[item.kind].label}: ${item.title} (${item.key}), ${item.state}. Press Enter for details`,
    };
  });
  const edges = graph.edges.map((edge) => ({ ...edge, selectable: false }));
  return { nodes, edges };
}
