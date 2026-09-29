// The tree view: /:project/tree (optionally rooted at ?goal=) and
// /:project/focus/:key. The session filter is ?session= with ?mode=.
import { useCallback, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { useDecisions, useSession, useTree } from '../api/queries.ts';
import { QueryState } from '../components/QueryState.tsx';
import { KeyLabel } from '../components/Titled.tsx';
import { TreeCanvas } from '../components/TreeCanvas.tsx';
import { TreeToolbar } from '../components/TreeToolbar.tsx';
import { useDrawer } from '../hooks/useDrawer.ts';
import { useTitles } from '../hooks/useTitles.ts';
import { filterMode, PARAM, withParam } from '../lib/search.ts';
import { applySessionFilter } from '../lib/sessionFilter.ts';
import { countByScope } from '../lib/tree.ts';

export function TreePage({ focus }: { focus: boolean }) {
  const { project = '', key = null } = useParams();
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const drawer = useDrawer();
  const tree = useTree(project);
  const decisions = useDecisions(project);
  const sessionKey = search.get(PARAM.session);
  const mode = filterMode(search.get(PARAM.mode));
  const session = useSession(project, sessionKey);
  const titles = useTitles(project);
  const [showDone, setShowDone] = useState(false);
  const [unfiledOpen, setUnfiledOpen] = useState(false);
  const rootKey = focus ? key : search.get(PARAM.goal);
  const decisionCounts = useMemo(
    () => countByScope(decisions.data?.decisions ?? []),
    [decisions.data],
  );
  const filter = useMemo(
    () =>
      session.data === undefined ? null : { linked: new Set(session.data.items), mode },
    [session.data, mode],
  );
  const onFocus = useCallback(
    (itemKey: string) => {
      void navigate({
        pathname: `/${project}/focus/${itemKey}`,
        search: withParam(search, PARAM.item, null),
      });
    },
    [navigate, project, search],
  );
  const onShowDone = useCallback(() => {
    setShowDone(true);
  }, []);
  const onToggleUnfiled = useCallback(() => {
    setUnfiledOpen((open) => !open);
  }, []);

  return (
    <section className="tree" aria-label="Item tree">
      <TreeToolbar
        prefix={project}
        showDone={showDone}
        onShowDone={setShowDone}
        truncated={tree.data?.truncated ?? false}
      />
      {focus && key !== null && (
        <p className="focus-bar">
          Focus: <KeyLabel itemKey={key} titles={titles} />{' '}
          <Link
            to={{
              pathname: `/${project}/tree`,
              search: withParam(search, PARAM.goal, null),
            }}
          >
            Show the whole tree
          </Link>
        </p>
      )}
      <QueryState query={tree} what="tree">
        {(view) => {
          const filtered = applySessionFilter(view.nodes, filter);
          return (
            <TreeCanvas
              entries={filtered.entries}
              rootKey={rootKey}
              decisionCounts={decisionCounts}
              highlight={filtered.highlight}
              showDone={showDone}
              unfiledOpen={unfiledOpen}
              onOpen={drawer.open}
              onFocus={onFocus}
              onShowDone={onShowDone}
              onToggleUnfiled={onToggleUnfiled}
            />
          );
        }}
      </QueryState>
    </section>
  );
}
