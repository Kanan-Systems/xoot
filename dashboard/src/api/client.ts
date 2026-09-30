// The only network access the dashboard makes: same-origin requests under
// /api/v1, with the HttpOnly login cookie the server set. Reads are GETs;
// writes are POST or PATCH with a JSON body, which the guard requires along
// with the cookie and the page's own Origin (the browser sends it).
import type { ErrorOutput } from './types.gen.ts';

export const API_BASE = '/api/v1';

export type Details = Readonly<Record<string, unknown>>;

export class ApiError extends Error {
  readonly status: number;
  readonly error: string;
  // Write errors carry structured facts; reads and guard refusals may not.
  readonly details: Details;

  constructor(status: number, error: string, message: string, details: Details = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.error = error;
    this.details = details;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

// Read errors have {error, message}; write errors add details.
function isErrorOutput(value: unknown): value is ErrorOutput & { details?: unknown } {
  return (
    isRecord(value) &&
    typeof value.error === 'string' &&
    typeof value.message === 'string'
  );
}

async function parse<T>(response: Response): Promise<T> {
  // A proxy page or an empty body is not JSON; the status still speaks.
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (isErrorOutput(body)) {
      const details = isRecord(body.details) ? body.details : {};
      throw new ApiError(response.status, body.error, body.message, details);
    }
    throw new ApiError(response.status, 'HttpError', `HTTP ${String(response.status)}`);
  }
  return body as T;
}

// The response type is trusted: the same server generated the schema.
export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'GET',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    ...(signal === undefined ? {} : { signal }),
  });
  return parse<T>(response);
}

export type WriteMethod = 'POST' | 'PATCH';

export async function sendJson<T>(
  method: WriteMethod,
  path: string,
  body: unknown,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return parse<T>(response);
}

export function segment(value: string): string {
  return encodeURIComponent(value);
}
