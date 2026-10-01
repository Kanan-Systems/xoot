// useTreeDrag against the real React Flow store, not a stand-in: nodes are
// controlled and their sizes come from measurement, as in the tree. A drop
// hands onNodeDragStop the node exactly as xyflow's getEventHandlerParams
// builds it: the user node (which never gains `measured`, since the tree
// ignores dimension changes) with the drag position. jsdom has no layout,
// so every node measures W x H, and the pane sits at the screen origin.
import { act, render, waitFor } from '@testing-library/react';
import {
  ReactFlow,
  type NodeTypes,
  type ReactFlowInstance,
  type Viewport,
} from '@xyflow/react';
import { expect, vi } from 'vitest';

import type { ItemKind } from '../api/types.gen.ts';
import { ItemNode } from '../components/ItemNode.tsx';
import { useTreeDrag, type FlowNode, type TreeDrag } from '../hooks/useTreeDrag.ts';
import { item } from './fixtures.ts';
import { mockReactFlowDom } from './reactFlow.ts';

const nodeTypes: NodeTypes = { item: ItemNode };
export const W = 260;
export const H = 128;

export const VIEWPORTS: Viewport[] = [
  { x: 0, y: 0, zoom: 1 },
  { x: 120, y: -40, zoom: 0.6 },
  { x: -300, y: 75, zoom: 1.4 },
];

export function measureNodes(): void {
  mockReactFlowDom();
  Object.defineProperties(HTMLElement.prototype, {
    offsetWidth: { configurable: true, get: () => W },
    offsetHeight: { configurable: true, get: () => H },
  });
}

export function flowItem(
  key: string,
  kind: ItemKind,
  parent: string | null,
  at: { x: number; y: number },
  collapsed = false,
): FlowNode {
  return {
    id: key,
    type: 'item',
    position: at,
    data: {
      item: item(key, kind, parent),
      hidden: {},
      fold:
        kind === 'goal' || kind === 'batch'
          ? { children: 1, open: 1, collapsed }
          : null,
      decisions: 0,
      blocked: null,
    },
  };
}

export interface Mounted {
  drag: () => TreeDrag;
  flow: () => ReactFlowInstance<FlowNode>;
  onDrop: ReturnType<typeof vi.fn<(item: unknown, parent: string) => string | null>>;
}

export async function mountFlow(
  nodes: FlowNode[],
  viewport: Viewport,
): Promise<Mounted> {
  const onDrop = vi.fn<(item: unknown, parent: string) => string | null>(() => null);
  const out: { drag: TreeDrag | null; flow: ReactFlowInstance<FlowNode> | null } = {
    drag: null,
    flow: null,
  };
  function Canvas() {
    const drag = useTreeDrag(onDrop);
    out.drag = drag;
    return (
      <ReactFlow<FlowNode>
        nodes={nodes}
        edges={[]}
        nodeTypes={nodeTypes}
        defaultViewport={viewport}
        nodesDraggable={false}
        onInit={(flow) => {
          out.flow = flow;
          drag.onInit(flow);
        }}
        onNodesChange={drag.onNodesChange}
      />
    );
  }
  render(<Canvas />);
  const first = nodes[0]?.id ?? '';
  await waitFor(() => {
    expect(out.flow?.getInternalNode(first)?.measured.width).toBe(W);
  });
  const need = <T,>(value: T | null): T => {
    if (value === null) {
      throw new Error('not mounted');
    }
    return value;
  };
  return { drag: () => need(out.drag), flow: () => need(out.flow), onDrop };
}

// Releases `key` with its top-left at `at` and the pointer at `pointer`
// (both in flow coordinates; the pointer defaults to the node's centre),
// converting the pointer to screen space through the viewport.
export function dropAt(
  mounted: Mounted,
  viewport: Viewport,
  key: string,
  at: { x: number; y: number },
  pointer = { x: at.x + W / 2, y: at.y + H / 2 },
): void {
  const internal = mounted.flow().getInternalNode(key);
  if (internal === undefined) {
    throw new Error(`no node ${key}`);
  }
  const dragged = { ...internal.internals.userNode, position: at, dragging: false };
  const event = new MouseEvent('mouseup', {
    clientX: pointer.x * viewport.zoom + viewport.x,
    clientY: pointer.y * viewport.zoom + viewport.y,
  });
  const drag = mounted.drag();
  act(() => {
    drag.onNodeDragStop(event, dragged, [dragged]);
  });
}
