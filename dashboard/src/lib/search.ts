// URL search parameters. Views are routes; what sits on top of a view (the
// drawer, the goal, the focus root, the filters) lives in the query string,
// so deep links and Back/Forward restore it. Nested keys such as
// goal-1/batch-2 always travel here, URL-encoded, never as a path segment.
export const PARAM = {
  item: 'item',
  // The create panel in the drawer slot; its only value is "goal".
  create: 'create',
  goal: 'goal',
  batch: 'batch',
  focus: 'focus',
  level: 'level',
  status: 'status',
} as const;

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
