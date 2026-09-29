// One tree node. The whole card is a button, so every node is reachable by
// keyboard; the category shows as colour, icon and state name together.
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';

import { categoryClass, categoryGlyph, KIND, truncate } from '../lib/display.ts';
import type { ItemNodeData } from '../lib/tree.ts';
import { useNodeActions } from './nodeActions.ts';

export type ItemFlowNode = Node<ItemNodeData, 'item'>;

export function ItemNode({ data }: NodeProps<ItemFlowNode>) {
  const { item, hiddenDone, decisions, highlighted, dimmed } = data;
  const actions = useNodeActions();
  const kind = KIND[item.kind];
  const category = categoryGlyph(item.category);
  const title = truncate(item.title);
  const classes = [
    'node',
    highlighted ? 'node-highlighted' : '',
    dimmed ? 'node-dimmed' : '',
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <div className={classes}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <button
        type="button"
        className="node-button"
        aria-label={`${kind.label} ${item.key}: ${item.title}, ${item.state}`}
        onClick={() => {
          actions.open(item.key);
        }}
      >
        <span className="node-head">
          <span className="node-kind" aria-hidden="true" title={kind.label}>
            {kind.icon}
          </span>
          <span className="node-key">{item.key}</span>
          {decisions > 0 && (
            <span
              className="badge badge-decisions"
              title={`${String(decisions)} decisions`}
            >
              ◆ {decisions}
            </span>
          )}
        </span>
        <span className="node-title" title={title.truncated ? item.title : undefined}>
          {title.text}
        </span>
        <span className={categoryClass(item.category)}>
          <span aria-hidden="true">{category.icon}</span> {item.state}
        </span>
      </button>
      {hiddenDone > 0 && (
        <button
          type="button"
          className="badge badge-done"
          onClick={actions.showDone}
          aria-label={`Show ${String(hiddenDone)} hidden done or dropped items`}
        >
          {hiddenDone} done
        </button>
      )}
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}
