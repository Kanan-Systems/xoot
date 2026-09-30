// A plan's changes as plain lines: each changed item's key, then every
// field that changes, old value to new. References are keys already.
import type { ChangeEntry } from '../api/types.gen.ts';

function text(value: unknown): string {
  if (value === null || value === undefined) {
    return 'none';
  }
  if (
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  ) {
    return String(value);
  }
  return JSON.stringify(value);
}

export function describeChange(change: ChangeEntry): string {
  const fields = Object.keys(change.after).filter(
    (field) => text(change.before[field]) !== text(change.after[field]),
  );
  if (fields.length === 0) {
    return change.key;
  }
  const parts = fields.map(
    (field) => `${field} ${text(change.before[field])} → ${text(change.after[field])}`,
  );
  return `${change.key}: ${parts.join('; ')}`;
}
