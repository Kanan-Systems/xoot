// Dragging the armed batch or subtask onto a new parent in the tree.
// Positions come from the layout, so the dragged node's position is held
// here while it moves and, after a drop onto an allowed parent, while that
// move waits for confirmation (shownDragged); otherwise it is released and
// the layout puts the node back. The target is decided from xyflow's own
// measured rectangles and the pointer, all in flow coordinates (flowDrop,
// dropTarget); anything else snaps back with a hint. The hint clears on
// Escape and after a drop; the canvas also clears it (say) on pointer-down
// and when a node is armed.
import type {
  NodeChange,
  OnNodeDrag,
  ReactFlowInstance,
  XYPosition,
} from '@xyflow/react';
import { useCallback, useEffect, useRef, useState } from 'react';

import type { ItemSummary } from '../api/types.gen.ts';
import type { ItemFlowNode } from '../components/ItemNode.tsx';
import type { ProjectFlowNode } from '../components/ProjectNode.tsx';
import { logDrop } from '../lib/dragDebug.ts';
import { decideDrop, NO_TARGET } from '../lib/dropTarget.ts';
import { dropScene } from '../lib/flowDrop.ts';

export type FlowNode = ItemFlowNode | ProjectFlowNode;

export interface Dragged {
  id: string;
  position: XYPosition;
}

// Takes a drop onto an allowed parent; returns why it was refused, if it was.
export type OnTreeDrop = (item: ItemSummary, parent: string) => string | null;

export interface TreeDrag {
  dragged: Dragged | null;
  // True while the pointer is dragging, false once dropped.
  active: boolean;
  message: string;
  say: (message: string) => void;
  onInit: (instance: ReactFlowInstance<FlowNode>) => void;
  onNodesChange: (changes: NodeChange<FlowNode>[]) => void;
  onNodeDragStart: OnNodeDrag<FlowNode>;
  onNodeDragStop: OnNodeDrag<FlowNode>;
}

export function useTreeDrag(onDrop: OnTreeDrop): TreeDrag {
  const instance = useRef<ReactFlowInstance<FlowNode> | null>(null);
  const [dragged, setDragged] = useState<Dragged | null>(null);
  const [active, setActive] = useState(false);
  const [message, setMessage] = useState('');

  const shown = message !== '';
  useEffect(() => {
    if (!shown) {
      return undefined;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMessage('');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
    };
  }, [shown]);

  const onInit = useCallback((flow: ReactFlowInstance<FlowNode>) => {
    instance.current = flow;
  }, []);

  const onNodesChange = useCallback((changes: NodeChange<FlowNode>[]) => {
    for (const change of changes) {
      if (change.type === 'position' && change.dragging === true && change.position) {
        setDragged({ id: change.id, position: change.position });
        setActive(true);
      }
    }
  }, []);

  const onNodeDragStart: OnNodeDrag<FlowNode> = useCallback(() => {
    setMessage('');
  }, []);

  const onNodeDragStop: OnNodeDrag<FlowNode> = useCallback(
    (event, node) => {
      setActive(false);
      const flow = instance.current;
      if (node.type !== 'item' || flow === null) {
        setDragged(null);
        setMessage(node.type === 'item' ? NO_TARGET : '');
        return;
      }
      const scene = dropScene(flow, node, event);
      const decision = decideDrop(scene.dragged, scene.candidates, scene.pointer);
      logDrop(node.id, scene, decision);
      const { result } = decision;
      // Held where it was dropped until the move is confirmed or not.
      const refused = result.ok ? onDrop(node.data.item, result.parent) : result.reason;
      setMessage(refused ?? '');
      if (refused !== null) {
        setDragged(null);
      }
    },
    [onDrop],
  );

  return {
    dragged,
    active,
    message,
    say: setMessage,
    onInit,
    onNodesChange,
    onNodeDragStart,
    onNodeDragStop,
  };
}

// The position to draw: while dragging, or for the node whose move waits.
export function shownDragged(drag: TreeDrag, held: string | null): Dragged | null {
  const { dragged } = drag;
  return dragged !== null && (drag.active || dragged.id === held) ? dragged : null;
}

// The layout's nodes with the one being dragged where the pointer has it.
export function withDragged<N extends { id: string; position: XYPosition }>(
  nodes: N[],
  dragged: Dragged | null,
): N[] {
  if (dragged === null) {
    return nodes;
  }
  return nodes.map((node) =>
    node.id === dragged.id ? { ...node, position: dragged.position } : node,
  );
}
