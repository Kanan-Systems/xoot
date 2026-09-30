// What a refused write means for the user. The server's message is safe
// text; details add structured facts (a version conflict's fields and
// actors, the open children that block a done, a plan's size).
import { ApiError, type Details } from '../api/client.ts';

// A two-phase write whose token or plan no longer holds starts over with a
// fresh preview instead of failing.
const RESTART = new Set(['PreviewRequired', 'ConfirmTokenError', 'StaleWriteError']);

export function isRestart(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409 && RESTART.has(error.error);
}

function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((entry): entry is string => typeof entry === 'string')
    : [];
}

function actorLabels(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((actor: unknown) => {
    if (typeof actor !== 'object' || actor === null) {
      return [];
    }
    const { kind, client } = actor as Record<string, unknown>;
    return typeof kind === 'string' && typeof client === 'string'
      ? [`${kind}/${client}`]
      : [];
  });
}

function scalar(value: unknown): string | null {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : null;
}

// Short lines summarising details; none when there is nothing to add.
export function detailLines(details: Details): string[] {
  const lines: string[] = [];
  const fields = strings(details.changed_fields);
  if (fields.length > 0) {
    lines.push(`Changed meanwhile: ${fields.join(', ')}.`);
  }
  const actors = actorLabels(details.actors);
  if (actors.length > 0) {
    lines.push(`Changed by: ${actors.join(', ')}.`);
  }
  const current = scalar(details.current_version);
  if (current !== null) {
    lines.push(`It is now at version ${current}; cancel to see it, then edit again.`);
  }
  const size = scalar(details.size);
  const cap = scalar(details.cap);
  if (size !== null && cap !== null) {
    lines.push(`The change touches ${size} items; the limit is ${cap}.`);
  }
  return lines;
}

// The open children a refused done or drop lists, if any.
export function openKeys(details: Details): string[] {
  return strings(details.open_keys);
}

export function headline(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Not signed in: open the URL that `xoot dashboard` printed.';
    }
    if (error.status === 413) {
      return 'The change is too large to send.';
    }
    return error.message;
  }
  return 'The change could not be sent.';
}
