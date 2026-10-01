// The tree view, /:project/tree. With no parameter it is the project-root
// tree; ?goal=<key> narrows it to one goal and ?focus=<key> roots it at any
// goal or batch. Both keys are nested paths, so they stay query parameters.
// Collapsed goals and batches are per viewer, kept in browser storage, and
// forgotten once a complete tree no longer has them. A double-clicked batch
// or subtask is armed for dragging; dropped onto a new parent, the move is
// confirmed in plain words before anything is sent (TreeMove).
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { useDecisions, useProjects, useTree } from '../api/queries.ts';
import type { ItemSummary, TreeEntry } from '../api/types.gen.ts';
import { QueryState } from '../components/QueryState.tsx';
import { KeyLabel } from '../components/Titled.tsx';
import { TreeCanvas } from '../components/TreeCanvas.tsx';
import { TreeMovePanel, useTreeMove } from '../components/TreeMove.tsx';
import { TreeToolbar } from '../components/TreeToolbar.tsx';
import { useCollapsed } from '../hooks/useCollapsed.ts';
import { useDrawer } from '../hooks/useDrawer.ts';
import { useTitles } from '../hooks/useTitles.ts';
import { PARAM, withParam } from '../lib/search.ts';
import { blockedCounts, countByOwner } from '../lib/tree.ts';

const NO_ENTRIES: readonly TreeEntry[] = [];

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
  const [notice, setNotice] = useState('');
  const collapsed = useCollapsed(project);
  const { prune } = collapsed;
  // Only a loaded, untruncated tree says which keys are really gone: a cut,
  // loading or failed one keeps every stored key.
  const complete = tree.isSuccess && !tree.data.truncated ? tree.data : null;
  useEffect(() => {
    if (complete !== null) {
      prune(new Set(complete.nodes.map((entry) => entry.item.key)));
    }
  }, [complete, prune]);
  const entries = tree.data?.nodes ?? NO_ENTRIES;
  const moving = useTreeMove(project, entries, titles, setNotice);
  // A double-click also clicked, opening the drawer: arming closes it again
  // without a history entry, so the canvas is free to drag on.
  const onArm = (item: ItemSummary) => {
    if (drawer.itemKey !== null) {
      drawer.dismiss();
    }
    return moving.arm(item);
  };
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
      >
        <button type="button" onClick={drawer.openCreate}>
          New goal
        </button>
      </TreeToolbar>
      <p role="status" className="notice">
        {notice}
      </p>
      <TreeMovePanel tree={moving} entries={entries} titles={titles} />
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
            collapsed={collapsed.keys}
            onOpen={drawer.open}
            onFocus={onFocus}
            onShowDone={onShowDone}
            onToggle={collapsed.toggle}
            armed={moving.state.armed}
            held={moving.state.pending?.item.key ?? null}
            onArm={onArm}
            onDisarm={moving.disarm}
            onDrop={moving.drop}
          />
        )}
      </QueryState>
    </section>
  );
}
