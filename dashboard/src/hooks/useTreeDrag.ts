// Dragging the armed batch or subtask onto a new parent in the tree.
// Positions come from the layout, so the dragged node's position is held
// here while it moves and, after a drop onto an allowed parent, while that
// move waits for confirmation (shownDragged); otherwise it is released and
// the layout puts the node back. The drop target is the first intersecting
// node the hierarchy allows; anything else is refused with a message.
import type {
  NodeChange,
  OnNodeDrag,
  ReactFlowInstance,
  XYPosition,
} from '@xyflow/react';
import { useCallback, useRef, useState } from 'react';

import type { ItemSummary } from '../api/types.gen.ts';
import type { ItemFlowNode } from '../components/ItemNode.tsx';
import type { ProjectFlowNode } from '../components/ProjectNode.tsx';
import { dropTarget } from '../lib/itemRules.ts';

export type FlowNode = ItemFlowNode | ProjectFlowNode;

export interface Dragged {
  id: string;
  position: XYPosition;
}

export interface TreeDrag {
  dragged: Dragged | null;
  // True while the pointer is dragging, false once dropped.
  active: boolean;
  message: string;
  onInit: (instance: ReactFlowInstance<FlowNode>) => void;
  onNodesChange: (changes: NodeChange<FlowNode>[]) => void;
  onNodeDragStart: OnNodeDrag<FlowNode>;
  onNodeDragStop: OnNodeDrag<FlowNode>;
}

function itemsOf(nodes: readonly FlowNode[]): ItemSummary[] {
  return nodes.flatMap((node) => (node.type === 'item' ? [node.data.item] : []));
}

export function useTreeDrag(
  onDrop: (item: ItemSummary, parent: string) => void,
): TreeDrag {
  const instance = useRef<ReactFlowInstance<FlowNode> | null>(null);
  const [dragged, setDragged] = useState<Dragged | null>(null);
  const [active, setActive] = useState(false);
  const [message, setMessage] = useState('');

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
    (_event, node) => {
      setActive(false);
      if (node.type !== 'item') {
        setDragged(null);
        return;
      }
      const hits = instance.current?.getIntersectingNodes(node) ?? [];
      const result = dropTarget(node.data.item, itemsOf(hits));
      if (result.ok) {
        // Held where it was dropped until the move is confirmed or not.
        onDrop(node.data.item, result.parent);
      } else {
        setDragged(null);
        setMessage(result.reason);
      }
    },
    [onDrop],
  );

  return {
    dragged,
    active,
    message,
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
