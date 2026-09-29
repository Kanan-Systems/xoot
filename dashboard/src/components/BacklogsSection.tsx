// The backlog view's tables: each open session, the project backlog, then
// unfiled subtasks.
import type { BacklogsView } from '../api/types.gen.ts';
import { backlogGroups } from '../lib/backlogGroups.ts';
import { ItemTable } from './ItemTable.tsx';

export function BacklogsSection({ view }: { view: BacklogsView }) {
  return (
    <>
      {backlogGroups(view).map((group) => (
        <section key={group.id} aria-labelledby={`backlog-${group.id}`}>
          <h2 id={`backlog-${group.id}`}>{group.heading}</h2>
          <ItemTable caption={group.heading} rows={group.items} holder created />
          {group.truncated && <p className="warning">Only the first 100 are shown.</p>}
        </section>
      ))}
    </>
  );
}
