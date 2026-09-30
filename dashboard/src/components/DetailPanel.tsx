// The drawer slot, shared by every view: full height on the right, holding
// an item's details or the new-goal panel, never both. Closed by its button
// or Escape; in an item's drawer, Escape from a form field is ignored so an
// edit is not lost to a stray key. It reads the item and the tree (for what
// open backlog blocks) of the current project, and holds the item's write
// controls.
import { useEffect, useRef } from 'react';

import { useItem, useTree } from '../api/queries.ts';
import { useDrawer } from '../hooks/useDrawer.ts';
import { useTitles } from '../hooks/useTitles.ts';
import { CreateItemForm } from './CreateForms.tsx';
import { ItemDetails } from './ItemDetails.tsx';
import { ItemWrite } from './ItemWrite.tsx';
import { QueryState } from './QueryState.tsx';

function isField(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement
  );
}

export function DetailPanel({ prefix }: { prefix: string }) {
  const { itemKey, creating, open, close } = useDrawer();
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (itemKey === null && creating === null) {
      return undefined;
    }
    // The create form focuses its own title field.
    if (itemKey !== null) {
      closeButton.current?.focus();
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && (creating !== null || !isField(event.target))) {
        close();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
    };
  }, [itemKey, creating, close]);
  if (itemKey === null && creating !== null) {
    return (
      <aside className="drawer" aria-label="New goal">
        <button type="button" className="drawer-close" onClick={close}>
          ✕ Close
        </button>
        <h2 className="detail-title">New goal</h2>
        <CreateItemForm
          prefix={prefix}
          kind="goal"
          parent={null}
          onDone={(_message, key) => {
            open(key);
          }}
          onCancel={close}
        />
      </aside>
    );
  }
  if (itemKey === null) {
    return null;
  }
  return (
    <aside className="drawer" aria-label={`Details of ${itemKey}`}>
      <button ref={closeButton} type="button" className="drawer-close" onClick={close}>
        ✕ Close
      </button>
      <DrawerItem key={itemKey} prefix={prefix} itemKey={itemKey} />
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
        >
          <ItemWrite prefix={prefix} view={view} />
        </ItemDetails>
      )}
    </QueryState>
  );
}
