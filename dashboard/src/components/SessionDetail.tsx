// One session, title first: its summary, its linked items grouped by outcome, its
// captures, and a way to see it in the tree.
import { Link } from 'react-router-dom';

import { useSession } from '../api/queries.ts';
import type { SessionView } from '../api/types.gen.ts';
import { PARAM } from '../lib/search.ts';
import { groupByOutcome } from '../lib/sessionGroups.ts';
import { ItemTable } from './ItemTable.tsx';
import { QueryState } from './QueryState.tsx';
import { KeyTag } from './Titled.tsx';

export function SessionDetail({
  prefix,
  sessionKey,
}: {
  prefix: string;
  sessionKey: string;
}) {
  const query = useSession(prefix, sessionKey);
  return (
    <section className="session-detail" aria-label={`Session ${sessionKey}`}>
      <QueryState query={query} what="session">
        {(view) => <SessionBody prefix={prefix} view={view} />}
      </QueryState>
    </section>
  );
}

export function SessionBody({ prefix, view }: { prefix: string; view: SessionView }) {
  const { session } = view;
  const inTree = new URLSearchParams({
    [PARAM.session]: session.key,
    [PARAM.mode]: 'highlight',
  });
  const captured = view.linked.filter((entry) => entry.captured).map((e) => e.item);
  return (
    <>
      <h2 className="detail-title">{session.title}</h2>
      <p className="detail-meta">
        Session <KeyTag value={session.key} /> {session.status}
      </p>
      <p>
        <Link
          className="action"
          to={{ pathname: `/${prefix}/tree`, search: `?${inTree.toString()}` }}
        >
          Show in tree
        </Link>
      </p>
      <h3>Summary</h3>
      {view.summary === null || view.summary === '' ? (
        <p className="muted">
          {session.status === 'open' ? 'Still open: no summary yet.' : 'No summary.'}
        </p>
      ) : (
        <pre className="body">{view.summary}</pre>
      )}
      <h3>What it covered</h3>
      <p className="muted">
        Done and dropped reflect each item&apos;s state now; dispositions are what the
        close decided.
      </p>
      {view.linked.length === 0 && <p className="muted">No linked items.</p>}
      {groupByOutcome(view.linked, session.status).map((group) => (
        <section key={group.outcome} aria-labelledby={`outcome-${group.outcome}`}>
          <h4 id={`outcome-${group.outcome}`}>
            {group.label} ({group.entries.length})
          </h4>
          <ItemTable caption={group.label} rows={group.entries.map((e) => e.item)} />
        </section>
      ))}
      <h3>Captured in this session ({captured.length})</h3>
      <ItemTable caption="Captured in this session" rows={captured} />
    </>
  );
}
