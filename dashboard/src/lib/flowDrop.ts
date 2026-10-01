// The drop as React Flow sees it, in flow coordinates. The tree's nodes are
// controlled and it ignores xyflow's dimension changes, so the user nodes
// handed to the drag handlers carry no `measured` or `width`: sizes and
// positions come from xyflow's internal nodes (getInternalNode), which hold
// what it measured. The handler's node position is already in flow space
// (tree nodes have no parent), and the pointer is converted from screen
// space with screenToFlowPosition, which accounts for pan and zoom.
import type { InternalNode, ReactFlowInstance, Viewport } from '@xyflow/react';

import type { ItemFlowNode } from '../components/ItemNode.tsx';
import type { FlowNode } from '../hooks/useTreeDrag.ts';
import type { Placed, Point, Rect } from './dropTarget.ts';
import { NODE_HEIGHT, NODE_WIDTH } from './layout.ts';

export type FlowView = Pick<
  ReactFlowInstance<FlowNode>,
  'getNodes' | 'getInternalNode' | 'screenToFlowPosition' | 'getViewport'
>;

export interface DropScene {
  dragged: Placed;
  candidates: Placed[];
  // The pointer where it was released, on screen and in the flow.
  screen: Point | null;
  pointer: Point | null;
  viewport: Viewport;
}

function rectOf(
  node: FlowNode,
  internal: InternalNode<FlowNode> | undefined,
  position?: Point,
): Rect {
  const at = position ?? internal?.internals.positionAbsolute ?? node.position;
  // The layout's size only when xyflow has not measured the node yet.
  return {
    x: at.x,
    y: at.y,
    width: internal?.measured.width ?? node.measured?.width ?? node.width ?? NODE_WIDTH,
    height:
      internal?.measured.height ?? node.measured?.height ?? node.height ?? NODE_HEIGHT,
  };
}

function placed(flow: FlowView, node: ItemFlowNode, position?: Point): Placed {
  return {
    item: node.data.item,
    rect: rectOf(node, flow.getInternalNode(node.id), position),
    folded: node.data.fold?.collapsed === true,
  };
}

// Where a mouse or touch was released, in screen (client) coordinates.
export function clientPoint(event: MouseEvent | TouchEvent): Point | null {
  const source = 'changedTouches' in event ? event.changedTouches[0] : event;
  if (source === undefined || !Number.isFinite(source.clientX)) {
    return null;
  }
  return { x: source.clientX, y: source.clientY };
}

export function dropScene(
  flow: FlowView,
  node: ItemFlowNode,
  event: MouseEvent | TouchEvent,
): DropScene {
  const screen = clientPoint(event);
  return {
    dragged: placed(flow, node, node.position),
    candidates: flow
      .getNodes()
      .flatMap((other) =>
        other.type === 'item' && other.id !== node.id ? [placed(flow, other)] : [],
      ),
    screen,
    pointer: screen === null ? null : flow.screenToFlowPosition(screen),
    viewport: flow.getViewport(),
  };
}
