// The backlog view: one section per level (batch, goal, project), each
// holding one collapsible table per batch or goal. A group heading is a
// button that collapses its table; all start expanded.
import { useState } from 'react';

import type { BacklogView } from '../api/types.gen.ts';
import {
  backlogGroups,
  LEVEL_HEADING,
  LEVEL_ORDER,
  type BacklogGroup,
} from '../lib/backlogGroups.ts';
import type { Titles } from '../lib/titles.ts';
import { BacklogTable } from './BacklogTable.tsx';
import { KeyTag, TitleText } from './Titled.tsx';

interface BacklogsSectionProps {
  view: BacklogView;
  titles: Titles;
}

export function BacklogsSection({ view, titles }: BacklogsSectionProps) {
  const groups = backlogGroups(view, titles);
  if (groups.length === 0) {
    return <p className="muted">No open backlog.</p>;
  }
  return (
    <>
      {LEVEL_ORDER.map((level) => {
        const inLevel = groups.filter((group) => group.level === level);
        if (inLevel.length === 0) {
          return null;
        }
        return (
          <section key={level} aria-labelledby={`level-${level}`}>
            <h2 id={`level-${level}`}>{LEVEL_HEADING[level]}</h2>
            {inLevel.map((group) => (
              <GroupSection key={group.id} group={group} titles={titles} />
            ))}
          </section>
        );
      })}
      {view.truncated && <p className="warning">Only the first 200 are shown.</p>}
    </>
  );
}

function heading(group: BacklogGroup): string {
  if (group.holders.length === 0) {
    return 'Project backlog';
  }
  return group.holders.map((holder) => holder.title ?? holder.key).join(' › ');
}

function GroupSection({ group, titles }: { group: BacklogGroup; titles: Titles }) {
  const [open, setOpen] = useState(true);
  const headingId = `backlog-${group.id}`;
  const panelId = `${headingId}-rows`;
  return (
    <section aria-labelledby={headingId}>
      <h3 id={headingId}>
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
          {group.holders.length === 0 ? (
            <TitleText title="Project backlog" />
          ) : (
            group.holders.map((holder, index) => (
              <span key={holder.key}>
                {index > 0 && <span aria-hidden="true"> › </span>}
                <TitleText title={holder.title ?? holder.key} />{' '}
                <KeyTag value={holder.key} />
              </span>
            ))
          )}{' '}
          <span className="count">({group.items.length})</span>
        </button>
      </h3>
      {open && (
        <div id={panelId}>
          <BacklogTable caption={heading(group)} rows={group.items} titles={titles} />
        </div>
      )}
    </section>
  );
}
