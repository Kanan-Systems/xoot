// The LTR tree. Nodes are not selectable. A double-click arms a batch or
// subtask, and only the armed node can be dragged, onto a new parent
// (useTreeDrag); the drawer's "Move to…" is the keyboard path, not React
// Flow's arrow-key nudging. onNodeClick is what gives React Flow's node
// wrappers pointer events (without a click handler it renders them with
// pointer-events: none, and clicks fall through to the pane). Item wrappers
// are focusable groups (a button role would hide the focus and badge buttons
// inside them): Enter or Space on one does what a click does. Double-click
// focuses a goal, so it does not zoom. The project node only draws and is
// not focusable.
import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type NodeMouseHandler,
  type NodeTypes,
} from '@xyflow/react';
import { useCallback, useMemo, type KeyboardEvent } from 'react';

import type { ItemSummary, TreeEntry } from '../api/types.gen.ts';
import {
  shownDragged,
  useTreeDrag,
  withDragged,
  type FlowNode,
  type OnTreeDrop,
} from '../hooks/useTreeDrag.ts';
import { KIND } from '../lib/display.ts';
import { isMovable } from '../lib/itemRules.ts';
import { layout } from '../lib/layout.ts';
import { blockedLine, buildGraph, type Graph } from '../lib/tree.ts';
import { ItemNode } from './ItemNode.tsx';
import { ProjectNode } from './ProjectNode.tsx';
import { NodeActionsContext } from './nodeActions.ts';

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
  // The armed node (the only one that can be dragged) and the node whose
  // drop waits for confirmation (drawn where it was dropped).
  armed?: string | null;
  held?: string | null;
  // Return why arming or the drop was refused, or null.
  onArm?: (item: ItemSummary) => string | null;
  onDisarm?: () => void;
  // The armed node dropped onto a parent the hierarchy allows.
  onDrop?: OnTreeDrop;
}

const NOTHING = () => undefined;
const ACCEPT = () => null;

export const ARMED_HINT = 'Drag it onto a new parent; Esc cancels.';

// A refused drop leaves the node armed, so its hint must win over the
// armed line or it would never be seen.
export function dragStatus(armed: string | null, held: string | null, message: string) {
  if (message !== '') {
    return message;
  }
  return armed !== null && held === null ? `${armed} is armed. ${ARMED_HINT}` : '';
}

// Only the armed node is draggable, and it says so.
function arm(nodes: FlowNode[], armed: string | null): FlowNode[] {
  if (armed === null) {
    return nodes;
  }
  return nodes.map((node) =>
    node.id === armed && node.type === 'item'
      ? {
          ...node,
          draggable: true,
          className: 'node-armed',
          ariaLabel: `${node.ariaLabel ?? ''} Armed: ${ARMED_HINT}`,
        }
      : node,
  );
}

export function TreeCanvas(props: TreeCanvasProps) {
  const { entries, rootKey, project, decisionCounts, blocked, showDone, collapsed } =
    props;
  const { onOpen, onFocus, onShowDone, onToggle } = props;
  const { armed = null, held = null, onArm = ACCEPT, onDisarm = NOTHING } = props;
  const drag = useTreeDrag(props.onDrop ?? ACCEPT);
  const { say } = drag;
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
  const laidOut = useMemo(() => toFlow(graph), [graph]);
  const flow = useMemo(
    () => ({ nodes: arm(laidOut.nodes, armed), edges: laidOut.edges }),
    [laidOut, armed],
  );
  const activate = useCallback(
    (node: FlowNode) => {
      if (node.type === 'item') {
        onOpen(node.id);
      }
    },
    [onOpen],
  );
  // The armed node is being moved: a click on it (or one ending a drag) must
  // not reopen the drawer that arming closed.
  const onNodeClick: NodeMouseHandler<FlowNode> = useCallback(
    (_event, node) => {
      if (node.id !== armed) {
        activate(node);
      }
    },
    [activate, armed],
  );
  // A double-click arms a batch or subtask for dragging; on a goal it still
  // focuses the tree on it.
  const onNodeDoubleClick: NodeMouseHandler<FlowNode> = useCallback(
    (_event, node) => {
      if (node.type !== 'item') {
        return;
      }
      if (isMovable(node.data.item.kind)) {
        say(onArm(node.data.item) ?? '');
      } else if (node.data.item.kind === 'goal') {
        onFocus(node.id);
      }
    },
    [onFocus, onArm, say],
  );
  // The last hint is stale once the user acts on the canvas again.
  const onPointerDown = useCallback(() => {
    say('');
  }, [say]);
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
      <p className="warning drop-message" role="status">
        {dragStatus(armed, held, drag.message)}
      </p>
      <ReactFlow<FlowNode>
        key={rootKey ?? 'all'}
        nodes={withDragged(flow.nodes, shownDragged(drag, held))}
        edges={flow.edges}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        nodesFocusable
        edgesFocusable={false}
        elementsSelectable={false}
        onInit={drag.onInit}
        onNodesChange={drag.onNodesChange}
        onNodeDragStart={drag.onNodeDragStart}
        onNodeDragStop={drag.onNodeDragStop}
        onNodeClick={onNodeClick}
        onNodeDoubleClick={onNodeDoubleClick}
        onPaneClick={onDisarm}
        onPointerDownCapture={onPointerDown}
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
        draggable: false,
        ariaLabel: `Project ${node.data.name}`,
      };
    }
    const { item, blocked, fold } = node.data;
    const held = blocked === null ? '' : `, ${blockedLine(blocked)}`;
    const hides =
      fold !== null && fold.open > 0 ? `, ${String(fold.open)} open children` : '';
    const folded = fold?.collapsed === true ? `, collapsed${hides}` : '';
    return {
      ...node,
      position,
      draggable: false,
      ariaLabel: `${KIND[item.kind].label}: ${item.title} (${item.key}), ${item.state}${held}${folded}. Press Enter for details`,
    };
  });
  const edges = graph.edges.map((edge) => ({ ...edge, selectable: false }));
  return { nodes, edges };
}
