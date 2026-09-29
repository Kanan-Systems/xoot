// The project tree: React Flow, laid out left to right by dagre.
import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type NodeTypes,
} from '@xyflow/react';
import { useMemo, useState } from 'react';

import type { DecisionSummary, TreeEntry } from '../api/types.gen.ts';
import { layout } from '../lib/layout.ts';
import { buildGraph, countByScope } from '../lib/tree.ts';
import { ItemNode, type ItemFlowNode } from './ItemNode.tsx';
import { UnfiledNode, type UnfiledFlowNode } from './UnfiledNode.tsx';
import { NodeActionsContext } from './nodeActions.ts';

const nodeTypes: NodeTypes = { item: ItemNode, unfiled: UnfiledNode };

interface TreeCanvasProps {
  entries: readonly TreeEntry[];
  truncated: boolean;
  decisions: readonly DecisionSummary[];
  focusKey: string | null;
  highlight: ReadonlySet<string> | null;
  onOpen: (key: string) => void;
}

export function TreeCanvas(props: TreeCanvasProps) {
  const { entries, truncated, decisions, focusKey, highlight, onOpen } = props;
  const [showDone, setShowDone] = useState(false);
  const decisionCounts = useMemo(() => countByScope(decisions), [decisions]);
  const graph = useMemo(
    () => buildGraph(entries, { showDone, focusKey, decisionCounts, highlight }),
    [entries, showDone, focusKey, decisionCounts, highlight],
  );
  const flow = useMemo(() => {
    const nodes: (ItemFlowNode | UnfiledFlowNode)[] = layout(
      graph.nodes,
      graph.edges,
    ).map(({ node, x, y }) => ({ ...node, position: { x, y } }));
    const edges: Edge[] = graph.edges.map((edge) => ({ ...edge, selectable: false }));
    return { nodes, edges };
  }, [graph]);
  const actions = useMemo(
    () => ({
      open: onOpen,
      showDone: () => {
        setShowDone(true);
      },
    }),
    [onOpen],
  );

  return (
    <section className="tree" aria-label="Item tree">
      <div className="tree-toolbar">
        <label>
          <input
            type="checkbox"
            checked={showDone}
            onChange={(event) => {
              setShowDone(event.target.checked);
            }}
          />{' '}
          Show done and dropped
        </label>
        {graph.hiddenTopLevel > 0 && (
          <span className="badge badge-done">
            {graph.hiddenTopLevel} done at top level
          </span>
        )}
        {truncated && <span className="warning">The tree was cut at 1000 items.</span>}
        {graph.focusMissing && (
          <span className="warning">The focused item is gone.</span>
        )}
      </div>
      <NodeActionsContext.Provider value={actions}>
        <ReactFlow
          key={focusKey ?? 'all'}
          nodes={flow.nodes}
          edges={flow.edges}
          nodeTypes={nodeTypes}
          nodesDraggable={false}
          nodesConnectable={false}
          nodesFocusable={false}
          edgesFocusable={false}
          elementsSelectable={false}
          fitView
          minZoom={0.1}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </NodeActionsContext.Provider>
    </section>
  );
}
