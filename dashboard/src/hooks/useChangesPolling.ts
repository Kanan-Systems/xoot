// Polls /changes and invalidates the project's queries when it moves.
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';

import { useChanges } from '../api/queries.ts';
import { changed, invalidateProject } from '../lib/polling.ts';

export interface PollStatus {
  checkedAt: number;
  failing: boolean;
}

export function useChangesPolling(prefix: string): PollStatus {
  const client = useQueryClient();
  const changes = useChanges(prefix);
  const latest = changes.data?.latest_event_id;
  const previous = useRef<{ prefix: string; latest: number | undefined }>({
    prefix,
    latest: undefined,
  });

  useEffect(() => {
    const seen = previous.current;
    // A project switch starts a new baseline rather than counting as a change.
    const before = seen.prefix === prefix ? seen.latest : undefined;
    previous.current = { prefix, latest };
    if (changed(before, latest)) {
      void invalidateProject(client, prefix);
    }
  }, [client, prefix, latest]);

  return { checkedAt: changes.dataUpdatedAt, failing: changes.isError };
}
