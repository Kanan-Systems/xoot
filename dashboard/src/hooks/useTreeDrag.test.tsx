// The drag handlers, driven directly with a stand-in instance: jsdom has no
// layout, so a real drag cannot be simulated. The stand-in has no internal
// nodes, so sizes fall back to the user nodes' own; the shape xyflow really
// hands the handlers is covered against the real store in
// useTreeDrag.xyflow.test.tsx and dropRules.xyflow.test.tsx.
import { act, renderHook } from '@testing-library/react';
import type { NodeChange, ReactFlowInstance } from '@xyflow/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ItemSummary } from '../api/types.gen.ts';
import { NO_TARGET } from '../lib/dropTarget.ts';
import { B1, B2, G1, G2, item } from '../test/fixtures.ts';
import {
  shownDragged,
  useTreeDrag,
  withDragged,
  type FlowNode,
  type OnTreeDrop,
} from './useTreeDrag.ts';

// A measured 200x60 node, at the origin unless placed elsewhere.
function flowNode(summary: ItemSummary, x = 0, y = 0): FlowNode {
  return {
    id: summary.key,
    type: 'item',
    position: { x, y },
    measured: { width: 200, height: 60 },
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
  const onMove = vi.fn<OnTreeDrop>(() => null);
  const { result } = renderHook(() => useTreeDrag(onMove));
  const instance = {
    getNodes: vi.fn(() => hits),
    getInternalNode: () => undefined,
    screenToFlowPosition: (point: { x: number; y: number }) => point,
    getViewport: () => ({ x: 0, y: 0, zoom: 1 }),
  };
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

  it('drops onto the allowed node it overlaps and holds it there for confirmation', () => {
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
    expect(instance.getNodes).toHaveBeenCalled();
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
    expect(result.current.message).toBe(NO_TARGET);
  });

  it('snaps back with the hint when a goal it touches only grazes it', () => {
    // xyflow reports the goal as intersecting: a 4px corner, in empty space.
    const { result, onMove } = setup([flowNode(item(G2, 'goal', null), 196, 56)]);
    act(() => {
      result.current.onNodesChange([
        { id: B2, type: 'position', position: { x: 0, y: 0 }, dragging: true },
      ]);
    });
    act(() => {
      result.current.onNodeDragStop(event, BATCH, [BATCH]);
    });
    expect(onMove).not.toHaveBeenCalled();
    expect(result.current.dragged).toBeNull();
    expect(result.current.message).toBe(NO_TARGET);
  });

  it('ignores a stop on the project node', () => {
    const { result, onMove, instance } = setup([]);
    act(() => {
      result.current.onNodeDragStop(event, PROJECT, [PROJECT]);
    });
    expect(instance.getNodes).not.toHaveBeenCalled();
    expect(onMove).not.toHaveBeenCalled();
  });
});

describe('the drop hint', () => {
  it('clears on Escape and after a successful drop', () => {
    const goal2 = flowNode(item(G2, 'goal', null));
    const { result, onMove } = setup([goal2]);
    act(() => {
      result.current.say(NO_TARGET);
    });
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    });
    expect(result.current.message).toBe('');
    act(() => {
      result.current.say(NO_TARGET);
    });
    act(() => {
      result.current.onNodeDragStop(event, BATCH, [BATCH]);
    });
    expect(onMove).toHaveBeenCalledWith(BATCH_ITEM, G2);
    expect(result.current.message).toBe('');
  });

  it('shows why the parent refused a drop and snaps back', () => {
    const { result, onMove } = setup([flowNode(item(G2, 'goal', null))]);
    onMove.mockReturnValue('The last move failed; dismiss it first.');
    act(() => {
      result.current.onNodeDragStop(event, BATCH, [BATCH]);
    });
    expect(result.current.message).toBe('The last move failed; dismiss it first.');
    expect(result.current.dragged).toBeNull();
  });
});

describe('the drag debug switch', () => {
  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  function dropOnGoal() {
    const info = vi.spyOn(console, 'info').mockImplementation(() => undefined);
    const { result } = setup([flowNode(item(G2, 'goal', null), 10, 10)]);
    act(() => {
      result.current.onNodeDragStop(event, BATCH, [BATCH]);
    });
    return info;
  }

  it('logs nothing by default', () => {
    expect(dropOnGoal()).not.toHaveBeenCalled();
  });

  it('logs nothing when storage throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(dropOnGoal()).not.toHaveBeenCalled();
  });

  it('logs the drop, its candidates and the decision when set', () => {
    localStorage.setItem('xoot:debug', 'net,drag');
    const info = dropOnGoal();
    expect(info).toHaveBeenCalledTimes(1);
    expect(info).toHaveBeenCalledWith('[xoot drag] drop', {
      dragged: { id: B2, rect: { x: 0, y: 0, width: 200, height: 60 } },
      pointer: { screen: { x: 0, y: 0 }, flow: { x: 0, y: 0 } },
      viewport: { x: 0, y: 0, zoom: 1 },
      candidates: [
        {
          key: G2,
          kind: 'goal',
          rect: { x: 10, y: 10, width: 200, height: 60 },
          overlap: 190 * 50,
          pointerInside: false,
          allowed: true,
          matches: true,
        },
      ],
      decision: { ok: true, parent: G2 },
      reason: `${G2}: the largest overlap`,
    });
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
