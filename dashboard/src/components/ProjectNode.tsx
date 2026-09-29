// The root of the project-root tree: every goal and every project-level
// backlog item hangs from it. It only draws; the drawer is for items.
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';

import type { ProjectNodeData } from '../lib/tree.ts';
import { HiddenBadges } from './HiddenBadges.tsx';

export type ProjectFlowNode = Node<ProjectNodeData, 'project'>;

export function ProjectNode({ data }: NodeProps<ProjectFlowNode>) {
  return (
    <div className="node node-project">
      <div className="node-card">
        <span className="node-title">
          <span className="node-kind" aria-hidden="true">
            ⌂
          </span>{' '}
          <span className="node-kind-label">Project</span> · {data.name}
        </span>
        <span className="node-meta">
          <span className="key">{data.prefix}</span>
        </span>
      </div>
      <HiddenBadges hidden={data.hidden} />
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}
