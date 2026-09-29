// URL search parameters. Views are routes; what sits on top of a view (the
// drawer, the session filter, the goal) lives in the query string, so deep
// links and Back/Forward restore it.
export const PARAM = {
  item: 'item',
  session: 'session',
  mode: 'mode',
  goal: 'goal',
  closed: 'closed',
  status: 'status',
} as const;

export type FilterMode = 'highlight' | 'only';

export function filterMode(value: string | null): FilterMode {
  return value === 'only' ? 'only' : 'highlight';
}

// The query string with one parameter set, or removed when value is null.
export function withParam(
  search: URLSearchParams,
  name: string,
  value: string | null,
): string {
  const next = new URLSearchParams(search);
  if (value === null) {
    next.delete(name);
  } else {
    next.set(name, value);
  }
  const text = next.toString();
  return text === '' ? '' : `?${text}`;
}
