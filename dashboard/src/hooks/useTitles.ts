// The title index for one project, from queries the views already share.
import { useMemo } from 'react';

import { useDecisions, useTree } from '../api/queries.ts';
import { titleIndex, type Titles } from '../lib/titles.ts';

export function useTitles(prefix: string): Titles {
  const tree = useTree(prefix);
  const decisions = useDecisions(prefix);
  return useMemo(
    () => titleIndex(tree.data, decisions.data),
    [tree.data, decisions.data],
  );
}
