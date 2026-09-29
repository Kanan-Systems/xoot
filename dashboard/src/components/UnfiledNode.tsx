// The group node every unfiled subtask hangs from. Clicking the node (or
// Enter/Space on it) expands or collapses the group; it starts collapsed.
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';

import type { UnfiledNodeData } from '../lib/tree.ts';
import { useNodeActions } from './nodeActions.ts';

export type UnfiledFlowNode = Node<UnfiledNodeData, 'unfiled'>;

export function UnfiledNode({ data }: NodeProps<UnfiledFlowNode>) {
  const actions = useNodeActions();
  return (
    <div className={`node node-group${data.dimmed ? ' node-dimmed' : ''}`}>
      <div className="node-head">
        <span className="node-kind" aria-hidden="true">
          {data.open ? '▾' : '▸'}
        </span>
        <span className="node-key">Unfiled</span>
      </div>
      <span className="node-title">
        {data.count} subtasks with no batch ({data.open ? 'shown' : 'collapsed'})
      </span>
      {data.hiddenDone > 0 && (
        <button
          type="button"
          className="badge badge-done"
          onClick={(event) => {
            event.stopPropagation();
            actions.showDone();
          }}
          aria-label={`Show ${String(data.hiddenDone)} hidden done or dropped items`}
        >
          {data.hiddenDone} done
        </button>
      )}
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}
