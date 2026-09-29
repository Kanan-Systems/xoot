import { fireEvent, render, screen } from '@testing-library/react';
import { ReactFlowProvider, type NodeProps } from '@xyflow/react';
import { describe, expect, it, vi } from 'vitest';

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

function renderNode(data: ItemFlowNode['data'], open = vi.fn(), showDone = vi.fn()) {
  render(
    <ReactFlowProvider>
      <NodeActionsContext.Provider value={{ open, showDone }}>
        <ItemNode {...props(data)} />
      </NodeActionsContext.Provider>
    </ReactFlowProvider>,
  );
  return { open, showDone };
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

  it('is a native, focusable button that opens the item', () => {
    const { open } = renderNode({ ...BASE, item: item('x-1', 'goal', null) });
    const button = screen.getByRole('button', { name: /Goal x-1/ });
    // A <button> is in the tab order and activates on Enter and Space natively.
    expect(button.tagName).toBe('BUTTON');
    expect(button).not.toHaveAttribute('tabindex');
    button.focus();
    expect(button).toHaveFocus();
    fireEvent.click(button);
    expect(open).toHaveBeenCalledWith('x-1');
  });

  it('marks overlay state with classes', () => {
    renderNode({ ...BASE, dimmed: true, item: item('x-1', 'goal', null) });
    expect(document.querySelector('.node')).toHaveClass('node-dimmed');
  });
});
