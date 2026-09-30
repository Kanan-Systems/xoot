// The goals and batches collapsed in one project's tree, loaded from and
// saved to this browser's storage on every toggle.
import { useCallback, useState } from 'react';

import { loadCollapsed, saveCollapsed } from '../lib/collapsed.ts';

export interface CollapsedState {
  keys: ReadonlySet<string>;
  toggle: (key: string) => void;
}

export function useCollapsed(project: string): CollapsedState {
  const [state, setState] = useState(() => ({ project, keys: loadCollapsed(project) }));
  // Switching project reloads during render instead of showing the other
  // project's set for one frame.
  if (state.project !== project) {
    setState({ project, keys: loadCollapsed(project) });
  }
  const toggle = useCallback((key: string) => {
    setState((current) => {
      const keys = new Set(current.keys);
      if (!keys.delete(key)) {
        keys.add(key);
      }
      saveCollapsed(current.project, keys);
      return { project: current.project, keys };
    });
  }, []);
  return { keys: state.project === project ? state.keys : new Set(), toggle };
}
