// The decisions grouped goal > batch > subtask. Every heading is a button
// that collapses its group (expanded unless this viewer collapsed it; the
// set is kept per project in browser storage). A goal's own decisions come
// before its batches; decisions whose owner is gone form the last group.
import type { ReactNode } from 'react';

import type { DecisionSummary } from '../api/types.gen.ts';
import {
  countOf,
  type DecisionHierarchy as Hierarchy,
  type DecisionNode,
} from '../lib/decisionGroups.ts';
import type { Titles } from '../lib/titles.ts';
import { CollapsibleGroup } from './CollapsibleGroup.tsx';
import { DecisionsSection } from './DecisionsSection.tsx';
import { KeyTag, TitleText } from './Titled.tsx';

// Keys never contain '@', so this cannot collide with an owner's key.
export const OWNERLESS = '@ownerless';

interface HierarchyProps {
  prefix: string;
  hierarchy: Hierarchy;
  successors: ReadonlyMap<string, string>;
  titles: Titles;
  collapsed: ReadonlySet<string>;
  onToggle: (key: string) => void;
}

export function DecisionHierarchy(props: HierarchyProps) {
  const { hierarchy } = props;
  return (
    <>
      {hierarchy.goals.map((node) => (
        <OwnerGroup key={node.key} node={node} depth={2} {...props} />
      ))}
      {hierarchy.ownerless.length > 0 && (
        <Group
          groupKey={OWNERLESS}
          depth={2}
          label="Owner gone"
          count={hierarchy.ownerless.length}
          decisions={hierarchy.ownerless}
          {...props}
        />
      )}
    </>
  );
}

function OwnerGroup(props: HierarchyProps & { node: DecisionNode; depth: number }) {
  const { node, depth, titles } = props;
  return (
    <Group
      {...props}
      groupKey={node.key}
      label={
        <>
          <TitleText title={titles.get(node.key) ?? node.key} />{' '}
          <KeyTag value={node.key} />
        </>
      }
      count={countOf(node)}
      decisions={node.decisions}
    >
      {node.children.map((child) => (
        <OwnerGroup key={child.key} {...props} node={child} depth={depth + 1} />
      ))}
    </Group>
  );
}

interface GroupProps extends HierarchyProps {
  groupKey: string;
  depth: number;
  label: ReactNode;
  count: number;
  decisions: readonly DecisionSummary[];
  children?: ReactNode;
}

function Group(props: GroupProps) {
  const { prefix, groupKey, depth, label, count, decisions, children } = props;
  const { successors, titles, collapsed, onToggle } = props;
  return (
    <CollapsibleGroup
      depth={depth}
      label={label}
      count={count}
      open={!collapsed.has(groupKey)}
      onToggle={() => {
        onToggle(groupKey);
      }}
      className="decision-group"
    >
      {decisions.length > 0 && (
        <DecisionsSection
          prefix={prefix}
          decisions={decisions}
          successors={successors}
          titles={titles}
        />
      )}
      {children}
    </CollapsibleGroup>
  );
}
