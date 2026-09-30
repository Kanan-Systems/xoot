// Dragging a batch or subtask onto a new parent in the tree. Positions come
// from the layout, so the dragged node's position is held here only while
// it moves; on drop it is released (the layout puts the node back, or puts
// it under its new parent once the move is written). The drop target is
// the first intersecting node the hierarchy allows; anything else is
// refused with a message.
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
  onMove: (item: ItemSummary, parent: string) => void,
): TreeDrag {
  const instance = useRef<ReactFlowInstance<FlowNode> | null>(null);
  const [dragged, setDragged] = useState<Dragged | null>(null);
  const [message, setMessage] = useState('');

  const onInit = useCallback((flow: ReactFlowInstance<FlowNode>) => {
    instance.current = flow;
  }, []);

  const onNodesChange = useCallback((changes: NodeChange<FlowNode>[]) => {
    for (const change of changes) {
      if (change.type === 'position' && change.dragging === true && change.position) {
        setDragged({ id: change.id, position: change.position });
      }
    }
  }, []);

  const onNodeDragStart: OnNodeDrag<FlowNode> = useCallback(() => {
    setMessage('');
  }, []);

  const onNodeDragStop: OnNodeDrag<FlowNode> = useCallback(
    (_event, node) => {
      setDragged(null);
      if (node.type !== 'item') {
        return;
      }
      const hits = instance.current?.getIntersectingNodes(node) ?? [];
      const result = dropTarget(node.data.item, itemsOf(hits));
      if (result.ok) {
        onMove(node.data.item, result.parent);
      } else {
        setMessage(result.reason);
      }
    },
    [onMove],
  );

  return { dragged, message, onInit, onNodesChange, onNodeDragStart, onNodeDragStop };
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
