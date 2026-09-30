// What one project's view has collapsed (the tree's goals and batches, the
// decisions view's headings), loaded from and saved to this browser's
// storage on every toggle and prune.
import { useCallback, useState } from 'react';

import {
  loadCollapsed,
  pruned,
  saveCollapsed,
  type CollapseView,
} from '../lib/collapsed.ts';

export interface CollapsedState {
  keys: ReadonlySet<string>;
  toggle: (key: string) => void;
  // Forgets stored keys that are not among these; the caller passes only a
  // complete, untruncated set of keys.
  prune: (existing: ReadonlySet<string>) => void;
}

export function useCollapsed(
  project: string,
  view: CollapseView = 'tree',
): CollapsedState {
  const [state, setState] = useState(() => ({
    project,
    keys: loadCollapsed(project, view),
  }));
  // Switching project reloads during render instead of showing the other
  // project's set for one frame.
  if (state.project !== project) {
    setState({ project, keys: loadCollapsed(project, view) });
  }
  const toggle = useCallback(
    (key: string) => {
      setState((current) => {
        const keys = new Set(current.keys);
        if (!keys.delete(key)) {
          keys.add(key);
        }
        saveCollapsed(current.project, keys, view);
        return { project: current.project, keys };
      });
    },
    [view],
  );
  const prune = useCallback(
    (existing: ReadonlySet<string>) => {
      setState((current) => {
        const keys = pruned(current.keys, existing);
        if (keys === null) {
          return current;
        }
        saveCollapsed(current.project, keys, view);
        return { project: current.project, keys };
      });
    },
    [view],
  );
  return { keys: state.project === project ? state.keys : new Set(), toggle, prune };
}
