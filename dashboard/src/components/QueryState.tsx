// Loading and error states for one query; renders children once data is in.
import type { UseQueryResult } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import { ApiError } from '../api/client.ts';

interface QueryStateProps<T> {
  query: UseQueryResult<T>;
  what: string;
  children: (data: T) => ReactNode;
}

export function QueryState<T>({ query, what, children }: QueryStateProps<T>) {
  if (query.data !== undefined) {
    return <>{children(query.data)}</>;
  }
  if (query.isError) {
    return <p role="alert">{errorText(query.error, what)}</p>;
  }
  return <p className="muted">Loading {what}…</p>;
}

export function errorText(error: unknown, what: string): string {
  if (error instanceof ApiError && error.status === 401) {
    return 'Not signed in: open the URL that `xoot dashboard` printed.';
  }
  if (error instanceof ApiError) {
    return `Could not load ${what}: ${error.message}`;
  }
  return `Could not load ${what}.`;
}
