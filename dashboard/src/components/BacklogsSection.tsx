// The backlog view's tables: each open session, the project backlog, then
// unfiled subtasks. Each group heading is a button that collapses its table;
// all start expanded.
import { useState } from 'react';

import type { BacklogsView } from '../api/types.gen.ts';
import { backlogGroups, type BacklogGroup } from '../lib/backlogGroups.ts';
import type { Titles } from '../lib/titles.ts';
import { ItemTable } from './ItemTable.tsx';
import { KeyTag, TitleText } from './Titled.tsx';

interface BacklogsSectionProps {
  view: BacklogsView;
  titles: Titles;
}

export function BacklogsSection({ view, titles }: BacklogsSectionProps) {
  return (
    <>
      {backlogGroups(view).map((group) => (
        <BacklogGroupSection key={group.id} group={group} titles={titles} />
      ))}
    </>
  );
}

function BacklogGroupSection({
  group,
  titles,
}: {
  group: BacklogGroup;
  titles: Titles;
}) {
  const [open, setOpen] = useState(true);
  const headingId = `backlog-${group.id}`;
  const panelId = `${headingId}-rows`;
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId}>
        <button
          type="button"
          className="group-toggle"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => {
            setOpen(!open);
          }}
        >
          <span aria-hidden="true">{open ? '▾' : '▸'}</span>{' '}
          <TitleText title={group.heading} />
          {group.key !== null && (
            <>
              {' '}
              <KeyTag value={group.key} />
            </>
          )}{' '}
          <span className="count">({group.items.length})</span>
        </button>
      </h2>
      {open && (
        <div id={panelId}>
          <ItemTable
            caption={group.heading}
            rows={group.items}
            holder
            created
            titles={titles}
          />
          {group.truncated && <p className="warning">Only the first 100 are shown.</p>}
        </div>
      )}
    </section>
  );
}
