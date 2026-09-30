// The drag handlers, driven directly: jsdom has no layout, so a real drag
// cannot be simulated; these prove what each handler does with what React
// Flow hands it.
import { act, renderHook } from '@testing-library/react';
import type { NodeChange, ReactFlowInstance } from '@xyflow/react';
import { describe, expect, it, vi } from 'vitest';

import type { ItemSummary } from '../api/types.gen.ts';
import { B1, B2, G1, G2, item } from '../test/fixtures.ts';
import {
  shownDragged,
  useTreeDrag,
  withDragged,
  type FlowNode,
} from './useTreeDrag.ts';

function flowNode(summary: ItemSummary): FlowNode {
  return {
    id: summary.key,
    type: 'item',
    position: { x: 0, y: 0 },
    data: { item: summary, hidden: {}, fold: null, decisions: 0, blocked: null },
  };
}

const PROJECT: FlowNode = {
  id: '@project',
  type: 'project',
  position: { x: 0, y: 0 },
  data: { name: 'X', prefix: 'x', hidden: {} },
};

function setup(hits: FlowNode[]) {
  const onMove = vi.fn();
  const { result } = renderHook(() => useTreeDrag(onMove));
  const instance = { getIntersectingNodes: vi.fn(() => hits) };
  act(() => {
    result.current.onInit(instance as unknown as ReactFlowInstance<FlowNode>);
  });
  return { result, onMove, instance };
}

const BATCH_ITEM = item(B2, 'batch', G1);
const BATCH = flowNode(BATCH_ITEM);
const event = new MouseEvent('mouseup');

describe('useTreeDrag', () => {
  it('holds the dragged position while it moves', () => {
    const { result } = setup([]);
    const change: NodeChange<FlowNode> = {
      id: B2,
      type: 'position',
      position: { x: 40, y: 50 },
      dragging: true,
    };
    act(() => {
      result.current.onNodesChange([
        change,
        { id: B1, type: 'select', selected: true },
      ]);
    });
    expect(result.current.dragged).toEqual({ id: B2, position: { x: 40, y: 50 } });
  });

  it('drops onto the first allowed node and holds it there for confirmation', () => {
    const goal2 = flowNode(item(G2, 'goal', null));
    const { result, onMove, instance } = setup([
      PROJECT,
      flowNode(item(B1, 'batch', G1)),
      goal2,
    ]);
    act(() => {
      result.current.onNodesChange([
        { id: B2, type: 'position', position: { x: 1, y: 1 }, dragging: true },
      ]);
    });
    act(() => {
      result.current.onNodeDragStop(event, BATCH, [BATCH]);
    });
    expect(instance.getIntersectingNodes).toHaveBeenCalledWith(BATCH);
    expect(onMove).toHaveBeenCalledWith(BATCH_ITEM, G2);
    // Drawn where it was dropped only while its move waits.
    expect(result.current.active).toBe(false);
    expect(shownDragged(result.current, B2)).toEqual({
      id: B2,
      position: { x: 1, y: 1 },
    });
    expect(shownDragged(result.current, null)).toBeNull();
    expect(result.current.message).toBe('');
  });

  it('snaps back with a message when the drop is not allowed', () => {
    const { result, onMove } = setup([flowNode(item(G1, 'goal', null))]);
    act(() => {
      result.current.onNodeDragStop(event, BATCH, [BATCH]);
    });
    expect(onMove).not.toHaveBeenCalled();
    expect(result.current.dragged).toBeNull();
    expect(result.current.message).toBe(`${B2} is already there.`);
    act(() => {
      result.current.onNodeDragStart(event, BATCH, [BATCH]);
    });
    expect(result.current.message).toBe('');
  });

  it('snaps back when dropped on nothing', () => {
    const { result, onMove } = setup([]);
    act(() => {
      result.current.onNodeDragStop(event, BATCH, [BATCH]);
    });
    expect(onMove).not.toHaveBeenCalled();
    expect(result.current.message).toMatch(/onto a goal/);
  });

  it('ignores a stop on the project node', () => {
    const { result, onMove, instance } = setup([]);
    act(() => {
      result.current.onNodeDragStop(event, PROJECT, [PROJECT]);
    });
    expect(instance.getIntersectingNodes).not.toHaveBeenCalled();
    expect(onMove).not.toHaveBeenCalled();
  });
});

describe('withDragged', () => {
  it('replaces only the dragged node position and keeps the array otherwise', () => {
    const nodes = [BATCH, PROJECT];
    expect(withDragged(nodes, null)).toBe(nodes);
    const moved = withDragged(nodes, { id: B2, position: { x: 9, y: 9 } });
    expect(moved[0]?.position).toEqual({ x: 9, y: 9 });
    expect(moved[1]).toBe(PROJECT);
  });
});
