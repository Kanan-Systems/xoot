// One project: sidebar, tree and, on /:project/item/:key, the detail panel.
// The selected session lives in ?session= so the overlay survives a reload.
import { useCallback, useMemo } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { useDecisions, useSession, useTree } from '../api/queries.ts';
import { DetailPanel } from '../components/DetailPanel.tsx';
import { LastUpdated } from '../components/LastUpdated.tsx';
import { QueryState } from '../components/QueryState.tsx';
import { Sidebar } from '../components/Sidebar.tsx';
import { TreeCanvas } from '../components/TreeCanvas.tsx';
import { useChangesPolling } from '../hooks/useChangesPolling.ts';

interface ProjectPageProps {
  mode: 'tree' | 'focus' | 'item';
}

export function ProjectPage({ mode }: ProjectPageProps) {
  const { project = '', key = null } = useParams();
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();
  const sessionKey = search.get('session');
  const poll = useChangesPolling(project);
  const tree = useTree(project);
  const decisions = useDecisions(project);
  const session = useSession(project, sessionKey);
  const highlight = useMemo(
    () => (session.data === undefined ? null : new Set(session.data.items)),
    [session.data],
  );
  const selectSession = useCallback(
    (next: string | null) => {
      setSearch(next === null ? {} : { session: next });
    },
    [setSearch],
  );
  const open = useCallback(
    (itemKey: string) => {
      void navigate({
        pathname: `/${project}/item/${itemKey}`,
        search: search.toString(),
      });
    },
    [navigate, project, search],
  );

  return (
    <div className="page">
      <header className="topbar">
        <h1>
          <Link to="/">xoot</Link> / {project}
        </h1>
        {mode === 'focus' && key !== null && (
          <p>
            Focus: {key} <Link to={`/${project}`}>Show the whole tree</Link>
          </p>
        )}
        <LastUpdated checkedAt={poll.checkedAt} failing={poll.failing} />
      </header>
      <Sidebar
        prefix={project}
        selectedSession={sessionKey}
        onSelectSession={selectSession}
      />
      <main className="main">
        <QueryState query={tree} what="tree">
          {(view) => (
            <TreeCanvas
              entries={view.nodes}
              truncated={view.truncated}
              decisions={decisions.data?.decisions ?? []}
              focusKey={mode === 'focus' ? key : null}
              highlight={highlight}
              onOpen={open}
            />
          )}
        </QueryState>
      </main>
      {mode === 'item' && key !== null && (
        <DetailPanel prefix={project} itemKey={key} />
      )}
    </div>
  );
}
