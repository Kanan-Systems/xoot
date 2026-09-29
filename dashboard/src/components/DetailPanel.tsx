// The detail drawer, shared by every view: full height on the right, closed
// by its button or Escape. It reads the item and the tree (for what open
// backlog blocks) of the current project.
import { useEffect, useRef } from 'react';

import { useItem, useTree } from '../api/queries.ts';
import { useDrawer } from '../hooks/useDrawer.ts';
import { useTitles } from '../hooks/useTitles.ts';
import { ItemDetails } from './ItemDetails.tsx';
import { QueryState } from './QueryState.tsx';

export function DetailPanel({ prefix }: { prefix: string }) {
  const { itemKey, close } = useDrawer();
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (itemKey === null) {
      return undefined;
    }
    closeButton.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        close();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
    };
  }, [itemKey, close]);
  if (itemKey === null) {
    return null;
  }
  return (
    <aside className="drawer" aria-label={`Details of ${itemKey}`}>
      <button ref={closeButton} type="button" className="drawer-close" onClick={close}>
        ✕ Close
      </button>
      <DrawerItem prefix={prefix} itemKey={itemKey} />
    </aside>
  );
}

function DrawerItem({ prefix, itemKey }: { prefix: string; itemKey: string }) {
  const query = useItem(prefix, itemKey);
  const tree = useTree(prefix);
  const titles = useTitles(prefix);
  return (
    <QueryState query={query} what="item">
      {(view) => (
        <ItemDetails
          prefix={prefix}
          view={view}
          titles={titles}
          openBacklog={
            tree.data?.blocked.find((b) => b.key === view.item.key)?.open_backlog
          }
        />
      )}
    </QueryState>
  );
}
