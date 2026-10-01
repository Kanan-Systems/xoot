// The backlog view, laid out like the Decisions tab: one indented staircase
// of collapsible headings, each goal (its own backlog, then a heading per
// batch under it), then the project backlog. Groups start expanded; what a
// viewer collapses is kept per project in browser storage.
// What a cover or push did is announced above the groups, since its row
// leaves the list.
import { useState } from 'react';

import type { BacklogRow, BacklogView } from '../api/types.gen.ts';
import {
  backlogTree,
  goalCount,
  PROJECT_GROUP,
  type BacklogFilter,
} from '../lib/backlogGroups.ts';
import { labelOf, type Titles } from '../lib/titles.ts';
import { BacklogList } from './BacklogList.tsx';
import { CollapsibleGroup } from './CollapsibleGroup.tsx';
import { KeyTag, TitleText } from './Titled.tsx';

interface BacklogsSectionProps {
  prefix: string;
  view: BacklogView;
  titles: Titles;
  filter: BacklogFilter;
  collapsed: ReadonlySet<string>;
  onToggle: (key: string) => void;
}

function Label({ itemKey, titles }: { itemKey: string; titles: Titles }) {
  return (
    <>
      <TitleText title={titles.get(itemKey) ?? itemKey} /> <KeyTag value={itemKey} />
    </>
  );
}

function emptyText(filter: BacklogFilter, titles: Titles): string {
  const chosen = filter.batch ?? filter.goal;
  return chosen === null
    ? 'No open backlog.'
    : `No open backlog under ${labelOf(chosen, titles)}.`;
}

export function BacklogsSection(props: BacklogsSectionProps) {
  const { prefix, view, titles, filter, collapsed, onToggle } = props;
  const [notice, setNotice] = useState('');
  const tree = backlogTree(view, filter);
  const title = (key: string) => titles.get(key) ?? key;
  const list = (label: string, rows: readonly BacklogRow[]) => (
    <BacklogList
      prefix={prefix}
      label={label}
      rows={rows}
      titles={titles}
      onDone={setNotice}
    />
  );
  const group = (key: string, depth: number) => ({
    depth,
    open: !collapsed.has(key),
    onToggle: () => {
      onToggle(key);
    },
    className: 'backlog-group',
  });
  const empty = tree.goals.length === 0 && tree.project.length === 0;
  return (
    <>
      <p role="status" className="notice">
        {notice}
      </p>
      {empty && <p className="muted">{emptyText(filter, titles)}</p>}
      {tree.goals.map((goal) => (
        <CollapsibleGroup
          key={goal.goal}
          {...group(goal.goal, 2)}
          label={<Label itemKey={goal.goal} titles={titles} />}
          count={goalCount(goal)}
        >
          {goal.items.length > 0 && list(title(goal.goal), goal.items)}
          {goal.batches.map((batch) => (
            <CollapsibleGroup
              key={batch.batch}
              {...group(batch.batch, 3)}
              label={<Label itemKey={batch.batch} titles={titles} />}
              count={batch.items.length}
            >
              {list(`${title(goal.goal)} › ${title(batch.batch)}`, batch.items)}
            </CollapsibleGroup>
          ))}
        </CollapsibleGroup>
      ))}
      {tree.project.length > 0 && (
        <CollapsibleGroup
          {...group(PROJECT_GROUP, 2)}
          label={<TitleText title="Project backlog" />}
          count={tree.project.length}
        >
          {list('Project backlog', tree.project)}
        </CollapsibleGroup>
      )}
      {view.truncated && <p className="warning">Only the first 200 are shown.</p>}
    </>
  );
}
