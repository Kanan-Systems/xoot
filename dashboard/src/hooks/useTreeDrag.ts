// Dragging the armed batch or subtask onto a new parent in the tree.
// Positions come from the layout, so the dragged node's position is held
// here while it moves and, after a drop onto an allowed parent, while that
// move waits for confirmation (shownDragged); otherwise it is released and
// the layout puts the node back. Of the nodes xyflow reports as
// intersecting, the target is the allowed one the dragged node overlaps
// most, past a minimum (dropTarget); anything else snaps back with a hint.
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
import { dropTarget, type Placed } from '../lib/dropTarget.ts';

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

// Tree nodes have no parent node, so a position is already absolute.
function placed(node: ItemFlowNode): Placed {
  return {
    item: node.data.item,
    rect: {
      ...node.position,
      width: node.measured?.width ?? node.width ?? 0,
      height: node.measured?.height ?? node.height ?? 0,
    },
  };
}

function placedItems(nodes: readonly FlowNode[]): Placed[] {
  return nodes.flatMap((node) => (node.type === 'item' ? [placed(node)] : []));
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
      const result = dropTarget(placed(node), placedItems(hits));
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
