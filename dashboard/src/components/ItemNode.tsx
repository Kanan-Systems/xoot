// One tree node. React Flow's node wrapper is the focusable, clickable
// element (see TreeCanvas); the card only draws the item. The title comes
// first, after the kind as icon and word; the key is secondary. The category
// shows as colour, icon and state name together. A backlog item has its own
// icon, word and dashed card. A goal or batch held open by backlog says so,
// with a read-only hint of what to ask for. A goal or batch with children
// folds them away; folded, it says how many it hides.
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import type { MouseEvent } from 'react';

import { categoryClass, categoryGlyph, KIND, truncate } from '../lib/display.ts';
import { blockedHint, blockedLine, type ItemNodeData } from '../lib/tree.ts';
import { HiddenBadges } from './HiddenBadges.tsx';
import { useNodeActions } from './nodeActions.ts';

export type ItemFlowNode = Node<ItemNodeData, 'item'>;

export function ItemNode({ data }: NodeProps<ItemFlowNode>) {
  const { item, hidden, fold, decisions, blocked } = data;
  const actions = useNodeActions();
  const kind = KIND[item.kind];
  const category = categoryGlyph(item.category);
  const title = truncate(item.title);
  const focusable = item.kind === 'goal' || item.kind === 'batch';
  const classes = ['node', `node-${item.kind}`, blocked === null ? '' : 'node-blocked']
    .filter(Boolean)
    .join(' ');
  const focus = (event: MouseEvent) => {
    event.stopPropagation();
    actions.focus(item.key);
  };
  const toggle = (event: MouseEvent) => {
    event.stopPropagation();
    actions.toggle(item.key);
  };
  const hint = blocked === null ? null : blockedHint(item.key, blocked);
  return (
    <div className={classes}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <div className="node-card">
        <span className="node-title">
          <span className="node-kind" aria-hidden="true" title={kind.label}>
            {kind.icon}
          </span>{' '}
          <span className="node-kind-label">{kind.label}</span> ·{' '}
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
              onClick={focus}
            >
              ⌖
            </button>
          )}
          {fold !== null && fold.children > 0 && (
            <button
              type="button"
              className="node-toggle"
              title={`${String(fold.children)} children`}
              aria-expanded={!fold.collapsed}
              aria-label={`${fold.collapsed ? 'Expand' : 'Collapse'} ${item.key}`}
              onClick={toggle}
            >
              {fold.collapsed ? `▸ ${String(fold.children)}` : '▾'}
            </button>
          )}
        </span>
        {blocked !== null && hint !== null && (
          <>
            <span className="node-blocked-line">
              <span aria-hidden="true">⚑</span> {blockedLine(blocked)}
            </span>
            <span className="node-hint" title={hint}>
              {hint}
            </span>
          </>
        )}
      </div>
      <HiddenBadges hidden={hidden} />
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}
