// The detail drawer is ?item=<key> on whatever view is showing: opening it
// pushes a history entry, so Back closes it and a deep link reopens it.
import { useCallback } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';

import { PARAM, withParam } from '../lib/search.ts';

export interface Drawer {
  itemKey: string | null;
  open: (key: string) => void;
  close: () => void;
  // Where a link to an item's drawer points, on the current view.
  hrefFor: (key: string) => { pathname: string; search: string };
}

export function useDrawer(): Drawer {
  const [search] = useSearchParams();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const hrefFor = useCallback(
    (key: string) => ({ pathname, search: withParam(search, PARAM.item, key) }),
    [pathname, search],
  );
  const open = useCallback(
    (key: string) => {
      void navigate(hrefFor(key));
    },
    [navigate, hrefFor],
  );
  const close = useCallback(() => {
    void navigate({ pathname, search: withParam(search, PARAM.item, null) });
  }, [navigate, pathname, search]);
  return { itemKey: search.get(PARAM.item), open, close, hrefFor };
}
