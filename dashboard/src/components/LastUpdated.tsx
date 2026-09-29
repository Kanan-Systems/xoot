// The live indicator: time since the last successful /changes poll, ticking
// every second, or a warning while polls fail.
import { useEffect, useState } from 'react';

import { ago } from '../lib/display.ts';

interface LastUpdatedProps {
  checkedAt: number;
  failing: boolean;
}

function useNow(everyMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => {
      setNow(Date.now());
    }, everyMs);
    return () => {
      clearInterval(timer);
    };
  }, [everyMs]);
  return now;
}

export function LastUpdated({ checkedAt, failing }: LastUpdatedProps) {
  const now = useNow(1000);
  const since =
    checkedAt === 0 ? null : ago(Math.max(0, Math.floor((now - checkedAt) / 1000)));
  if (failing) {
    return (
      <p className="live warning" role="status">
        ⚠ Live updates failing
        {since === null ? '' : `; last success ${since}`}
      </p>
    );
  }
  if (since === null) {
    return <p className="live muted">Connecting…</p>;
  }
  return (
    <p className="live" title={new Date(checkedAt).toLocaleTimeString()}>
      <span className="live-dot" aria-hidden="true">
        ●
      </span>{' '}
      Live, checked {since}
    </p>
  );
}
