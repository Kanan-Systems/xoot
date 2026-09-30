import { fireEvent, render, screen } from '@testing-library/react';
import { ReactFlowProvider, type NodeProps } from '@xyflow/react';
import { describe, expect, it, onTestFinished, vi } from 'vitest';

import { B1, B1_BACKLOG, G1, item } from '../test/fixtures.ts';
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
      <NodeActionsContext.Provider value={{ focus, showDone, toggle: vi.fn() }}>
        <ItemNode {...props(data)} />
      </NodeActionsContext.Provider>
    </ReactFlowProvider>,
  );
  return { focus, showDone, outer };
}

const BASE = { hidden: {}, fold: null, decisions: 0, blocked: null };

describe('ItemNode', () => {
  it('shows the key, kind icon, title and state with its category icon', () => {
    renderNode({ ...BASE, item: item(G1, 'goal', null, 'active', 'Ship it') });
    expect(screen.getByText(G1)).toBeInTheDocument();
    expect(screen.getByTitle('Goal')).toHaveTextContent('◎');
    expect(screen.getByText('Ship it')).not.toHaveAttribute('title');
    const state = screen.getByText('active', { exact: false });
    expect(state).toHaveClass('cat', 'cat-active');
    expect(state).toHaveTextContent('▶ active');
  });

  it('truncates a long title and keeps the full text on hover', () => {
    renderNode({ ...BASE, item: item(B1, 'batch', G1, 'open', LONG) });
    const title = screen.getByTitle(LONG);
    expect(title.textContent).toHaveLength(60);
    expect(title.textContent.endsWith('…')).toBe(true);
  });

  it('leads with "kind · title"; the key is secondary, after it', () => {
    renderNode({ ...BASE, item: item(B1, 'batch', G1, 'open', 'B4 dashboard') });
    const primary = document.querySelector('.node-title');
    expect(primary).toHaveTextContent(/^▤ Batch · B4 dashboard$/);
    const key = screen.getByText(B1);
    expect(key).toHaveClass('key');
    expect(primary?.compareDocumentPosition(key)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  it('draws a backlog item distinctly: its own icon, word and class', () => {
    renderNode({ ...BASE, item: item(B1_BACKLOG, 'backlog', B1) });
    expect(document.querySelector('.node')).toHaveClass('node-backlog');
    expect(screen.getByTitle('Backlog')).toHaveTextContent('⚑');
    expect(screen.getByText('Backlog')).toHaveClass('node-kind-label');
    expect(screen.queryByRole('button', { name: /Focus on/ })).toBeNull();
  });

  it('says what blocks a batch and hints what to ask, without a button', () => {
    renderNode({
      ...BASE,
      item: item(B1, 'batch', G1),
      blocked: { count: 1, children: 'subtasks', backlog: [B1_BACKLOG] },
    });
    expect(document.querySelector('.node')).toHaveClass('node-blocked');
    expect(
      screen.getByText('all subtasks done · 1 backlog open', { exact: false }),
    ).toBeInTheDocument();
    const hint = screen.getByText(`Ask Claude to cover or push ${B1_BACKLOG}`);
    expect(hint.tagName).not.toBe('BUTTON');
    expect(screen.getAllByRole('button')).toHaveLength(1);
  });

  it('badges hidden children by category, each with its own label', () => {
    renderNode({
      ...BASE,
      decisions: 3,
      hidden: { done: 2, dropped: 1 },
      item: item(B1, 'batch', G1),
    });
    expect(screen.getByTitle('3 decisions')).toHaveTextContent('◆ 3');
    expect(
      screen.getByRole('button', { name: 'Show 2 hidden done items' }),
    ).toHaveTextContent('✓ 2 done');
    expect(
      screen.getByRole('button', { name: 'Show 1 hidden dropped items' }),
    ).toHaveTextContent('✕ 1 dropped');
  });

  it('never labels dropped items as done', () => {
    renderNode({ ...BASE, hidden: { dropped: 2 }, item: item(B1, 'batch', G1) });
    expect(screen.queryByText(/done/)).toBeNull();
    expect(
      screen.getByRole('button', { name: /2 hidden dropped/ }),
    ).toBeInTheDocument();
  });

  it('has a focus button on goals and batches only; its click stays inside', () => {
    const { focus, outer } = renderNode({ ...BASE, item: item(G1, 'goal', null) });
    fireEvent.click(screen.getByRole('button', { name: `Focus on ${G1}` }));
    expect(focus).toHaveBeenCalledWith(G1);
    expect(outer).not.toHaveBeenCalled();
  });

  it('has no focus button on a subtask', () => {
    renderNode({ ...BASE, item: item('goal-1/batch-1/subtask-1', 'subtask', B1) });
    expect(screen.queryByRole('button', { name: /Focus on/ })).toBeNull();
  });

  it('a hidden badge shows closed items without opening the node', () => {
    const { showDone, outer } = renderNode({
      ...BASE,
      hidden: { done: 1 },
      item: item(G1, 'goal', null),
    });
    fireEvent.click(screen.getByRole('button', { name: /Show 1 hidden/ }));
    expect(showDone).toHaveBeenCalledTimes(1);
    expect(outer).not.toHaveBeenCalled();
  });
});
