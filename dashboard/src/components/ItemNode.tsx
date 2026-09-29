// One tree node. React Flow's node wrapper is the focusable, clickable
// element (see TreeCanvas); the card only draws the item. The title comes
// first, after the kind as icon and word; the key is secondary. The category
// shows as colour, icon and state name together.
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import type { MouseEvent } from 'react';

import { categoryClass, categoryGlyph, KIND, truncate } from '../lib/display.ts';
import type { ItemNodeData } from '../lib/tree.ts';
import { useNodeActions } from './nodeActions.ts';

export type ItemFlowNode = Node<ItemNodeData, 'item'>;

// Inner buttons act alone: their click must not also open the drawer.
function only(action: () => void) {
  return (event: MouseEvent) => {
    event.stopPropagation();
    action();
  };
}

export function ItemNode({ data }: NodeProps<ItemFlowNode>) {
  const { item, hiddenDone, decisions, highlighted, dimmed } = data;
  const actions = useNodeActions();
  const kind = KIND[item.kind];
  const category = categoryGlyph(item.category);
  const title = truncate(item.title);
  const focusable = item.kind === 'goal' || item.kind === 'batch';
  const classes = [
    'node',
    `node-${item.kind}`,
    highlighted ? 'node-highlighted' : '',
    dimmed ? 'node-dimmed' : '',
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <div className={classes}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <div className="node-card">
        <span className="node-title">
          <span className="node-kind" aria-hidden="true" title={kind.label}>
            {kind.icon}
          </span>{' '}
          <span className="node-kind-label">{item.kind}</span> ·{' '}
          <span title={title.truncated ? item.title : undefined}>{title.text}</span>
        </span>
        <span className="node-meta">
          <span className="key">{item.key}</span>
          <span className={categoryClass(item.category)}>
            <span aria-hidden="true">{category.icon}</span> {item.state}
          </span>
          {decisions > 0 && (
            <span
              className="badge badge-decisions"
              title={`${String(decisions)} decisions`}
            >
              ◆ {decisions}
            </span>
          )}
          {focusable && (
            <button
              type="button"
              className="node-focus"
              title={`Focus on this ${item.kind}`}
              aria-label={`Focus on ${item.key}`}
              onClick={only(() => {
                actions.focus(item.key);
              })}
            >
              ⌖
            </button>
          )}
        </span>
      </div>
      {hiddenDone > 0 && (
        <button
          type="button"
          className="badge badge-done"
          onClick={only(actions.showDone)}
          aria-label={`Show ${String(hiddenDone)} hidden done or dropped items`}
        >
          {hiddenDone} done
        </button>
      )}
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}
