// The right-hand drawer slot holds one panel at a time: an item's details
// (?item=<key>) or the new-goal panel (?create=goal). Opening either clears
// the other; opening pushes a history entry, so Back closes it and a deep
// link reopens it.
import { useCallback } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';

import { PARAM, withParam } from '../lib/search.ts';

export interface Drawer {
  itemKey: string | null;
  // The kind the create panel makes, when it is open instead of an item.
  creating: 'goal' | null;
  open: (key: string) => void;
  openCreate: () => void;
  close: () => void;
  // Closes without a history entry, for a close the user did not ask for.
  dismiss: () => void;
  // Where a link to an item's drawer points, on the current view.
  hrefFor: (key: string) => { pathname: string; search: string };
}

function without(search: URLSearchParams, name: string): URLSearchParams {
  return new URLSearchParams(withParam(search, name, null));
}

export function useDrawer(): Drawer {
  const [search] = useSearchParams();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const itemKey = search.get(PARAM.item);
  const creating =
    itemKey === null && search.get(PARAM.create) === 'goal' ? 'goal' : null;
  const hrefFor = useCallback(
    (key: string) => ({
      pathname,
      search: withParam(without(search, PARAM.create), PARAM.item, key),
    }),
    [pathname, search],
  );
  const open = useCallback(
    (key: string) => {
      // A double-click clicks twice: the second must not stack a history
      // entry for the drawer that is already open.
      if (key !== itemKey) {
        void navigate(hrefFor(key));
      }
    },
    [navigate, hrefFor, itemKey],
  );
  const openCreate = useCallback(() => {
    void navigate({
      pathname,
      search: withParam(without(search, PARAM.item), PARAM.create, 'goal'),
    });
  }, [navigate, pathname, search]);
  const close = useCallback(() => {
    void navigate({
      pathname,
      search: withParam(without(search, PARAM.item), PARAM.create, null),
    });
  }, [navigate, pathname, search]);
  const dismiss = useCallback(() => {
    void navigate(
      { pathname, search: withParam(without(search, PARAM.item), PARAM.create, null) },
      { replace: true },
    );
  }, [navigate, pathname, search]);
  return { itemKey, creating, open, openCreate, close, dismiss, hrefFor };
}
