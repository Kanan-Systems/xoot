// The tree view, /:project/tree. With no parameter it is the project-root
// tree; ?goal=<key> narrows it to one goal and ?focus=<key> roots it at any
// goal or batch. Both keys are nested paths, so they stay query parameters.
import { useCallback, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { useDecisions, useProjects, useTree } from '../api/queries.ts';
import { QueryState } from '../components/QueryState.tsx';
import { KeyLabel } from '../components/Titled.tsx';
import { TreeCanvas } from '../components/TreeCanvas.tsx';
import { TreeToolbar } from '../components/TreeToolbar.tsx';
import { useDrawer } from '../hooks/useDrawer.ts';
import { useTitles } from '../hooks/useTitles.ts';
import { PARAM, withParam } from '../lib/search.ts';
import { blockedCounts, countByOwner } from '../lib/tree.ts';

export function TreePage() {
  const { project = '' } = useParams();
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const drawer = useDrawer();
  const tree = useTree(project);
  const decisions = useDecisions(project);
  const projects = useProjects();
  const titles = useTitles(project);
  const [showDone, setShowDone] = useState(false);
  const focus = search.get(PARAM.focus);
  const rootKey = focus ?? search.get(PARAM.goal);
  const name =
    projects.data?.projects.find((p) => p.key_prefix === project)?.name ?? project;
  const projectInfo = useMemo(() => ({ name, prefix: project }), [name, project]);
  const decisionCounts = useMemo(
    () => countByOwner(decisions.data?.decisions ?? []),
    [decisions.data],
  );
  const blocked = useMemo(() => blockedCounts(tree.data?.blocked ?? []), [tree.data]);
  const onFocus = useCallback(
    (key: string) => {
      const kept = new URLSearchParams(withParam(search, PARAM.item, null));
      void navigate({ search: withParam(kept, PARAM.focus, key) });
    },
    [navigate, search],
  );
  const onShowDone = useCallback(() => {
    setShowDone(true);
  }, []);

  return (
    <section className="tree" aria-label="Item tree">
      <TreeToolbar
        showDone={showDone}
        onShowDone={setShowDone}
        truncated={tree.data?.truncated ?? false}
      />
      {focus !== null && (
        <p className="focus-bar">
          Focus: <KeyLabel itemKey={focus} titles={titles} />{' '}
          <Link to={{ search: withParam(search, PARAM.focus, null) }}>
            {search.get(PARAM.goal) === null ? 'Show the whole tree' : 'Show the goal'}
          </Link>
        </p>
      )}
      <QueryState query={tree} what="tree">
        {(view) => (
          <TreeCanvas
            entries={view.nodes}
            rootKey={rootKey}
            project={projectInfo}
            decisionCounts={decisionCounts}
            blocked={blocked}
            showDone={showDone}
            onOpen={drawer.open}
            onFocus={onFocus}
            onShowDone={onShowDone}
          />
        )}
      </QueryState>
    </section>
  );
}
