import { fireEvent, render, screen } from '@testing-library/react';
import { ReactFlowProvider, type NodeProps } from '@xyflow/react';
import { describe, expect, it, onTestFinished, vi } from 'vitest';

import { item } from '../test/fixtures.ts';
import { ItemNode, type ItemFlowNode } from './ItemNode.tsx';
import { NodeActionsContext } from './nodeActions.ts';

const LONG =
  'A very long title that goes on and on well past the sixty character limit';

function props(data: ItemFlowNode['data']): NodeProps<ItemFlowNode> {
  return {
    id: data.item.key,
    type: 'item',
    data,
    selected: false,
    dragging: false,
    draggable: false,
    selectable: false,
    deletable: false,
    isConnectable: false,
    zIndex: 0,
    positionAbsoluteX: 0,
    positionAbsoluteY: 0,
  };
}

function renderNode(data: ItemFlowNode['data'], focus = vi.fn(), showDone = vi.fn()) {
  // Stands in for the node wrapper: an inner button's click must not
  // propagate out of the node.
  const outer = vi.fn();
  document.addEventListener('click', outer);
  onTestFinished(() => {
    document.removeEventListener('click', outer);
  });
  render(
    <ReactFlowProvider>
      <NodeActionsContext.Provider value={{ focus, showDone }}>
        <ItemNode {...props(data)} />
      </NodeActionsContext.Provider>
    </ReactFlowProvider>,
  );
  return { focus, showDone, outer };
}

const BASE = { hiddenDone: 0, decisions: 0, highlighted: false, dimmed: false };

describe('ItemNode', () => {
  it('shows the key, kind icon, title and state with its category icon', () => {
    renderNode({ ...BASE, item: item('x-1', 'goal', null, 'active', 'Ship it') });
    expect(screen.getByText('x-1')).toBeInTheDocument();
    expect(screen.getByTitle('Goal')).toHaveTextContent('◎');
    expect(screen.getByText('Ship it')).not.toHaveAttribute('title');
    const state = screen.getByText('active', { exact: false });
    expect(state).toHaveClass('cat', 'cat-active');
    expect(state).toHaveTextContent('▶ active');
  });

  it('truncates a long title and keeps the full text on hover', () => {
    renderNode({ ...BASE, item: item('x-2', 'batch', 'x-1', 'open', LONG) });
    const title = screen.getByTitle(LONG);
    expect(title.textContent).toHaveLength(60);
    expect(title.textContent.endsWith('…')).toBe(true);
  });

  it('shows the decision badge and the hidden-done badge only when non-zero', () => {
    renderNode({
      ...BASE,
      decisions: 3,
      hiddenDone: 2,
      item: item('x-1', 'goal', null),
    });
    expect(screen.getByTitle('3 decisions')).toHaveTextContent('◆ 3');
    expect(
      screen.getByRole('button', { name: 'Show 2 hidden done or dropped items' }),
    ).toHaveTextContent('2 done');
  });

  it('shows the kind as a word as well as an icon', () => {
    renderNode({ ...BASE, item: item('x-2', 'batch', 'x-1') });
    expect(screen.getByText('Batch')).toHaveClass('node-kind-label');
  });

  it('has a focus button on goals and batches only; its click stays inside', () => {
    const { focus, outer } = renderNode({ ...BASE, item: item('x-1', 'goal', null) });
    fireEvent.click(screen.getByRole('button', { name: 'Focus on x-1' }));
    expect(focus).toHaveBeenCalledWith('x-1');
    expect(outer).not.toHaveBeenCalled();
  });

  it('has no focus button on a subtask', () => {
    renderNode({ ...BASE, item: item('x-3', 'subtask', 'x-2') });
    expect(screen.queryByRole('button', { name: /Focus on/ })).toBeNull();
  });

  it('the hidden-done badge shows done items without opening the node', () => {
    const { showDone, outer } = renderNode({
      ...BASE,
      hiddenDone: 1,
      item: item('x-1', 'goal', null),
    });
    fireEvent.click(screen.getByRole('button', { name: /Show 1 hidden/ }));
    expect(showDone).toHaveBeenCalledTimes(1);
    expect(outer).not.toHaveBeenCalled();
  });

  it('marks overlay state with classes', () => {
    renderNode({ ...BASE, dimmed: true, item: item('x-1', 'goal', null) });
    expect(document.querySelector('.node')).toHaveClass('node-dimmed');
  });
});
