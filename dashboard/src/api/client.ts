// The only network access the dashboard makes: same-origin GETs under
// /api/v1, with the HttpOnly login cookie the server set.
import type { ErrorOutput } from './types.gen.ts';

export const API_BASE = '/api/v1';

export class ApiError extends Error {
  readonly status: number;
  readonly error: string;

  constructor(status: number, error: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.error = error;
  }
}

function isErrorOutput(value: unknown): value is ErrorOutput {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as Record<string, unknown>).error === 'string' &&
    typeof (value as Record<string, unknown>).message === 'string'
  );
}

// The response type is trusted: the same server generated the schema.
export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'GET',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    ...(signal === undefined ? {} : { signal }),
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (isErrorOutput(body)) {
      throw new ApiError(response.status, body.error, body.message);
    }
    throw new ApiError(response.status, 'HttpError', `HTTP ${String(response.status)}`);
  }
  return body as T;
}

export function segment(value: string): string {
  return encodeURIComponent(value);
}
